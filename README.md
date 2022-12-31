This is a minimal proof of concept to remotely open a root shell on a Zyxel IP enabled camera. Known vulnerable models are

* Zyxel IPC-2605
* Zyxel IPC-3605N
* Zyxel IPC-4605N

# Pwning IPC-3605 and IPC-4605

Usage requires python3.9 or newer

```
python3.9 ./zyxel_ipc_camera_pwn.py 10.0.0.1
```

Where `10.0.0.1` is replaced with IP or hostname of the camera you want to pwn. Running this script will add a telnet server listening on port 15555
that logs you in as root. The device reboots as part of the exploit process. You can then connect via telnet.

# Pwning IPC-2605

The usage is identical for this camera, but one additional environmental variable needs to be set

```
PWN_2605=1 python3.9 ./zyxel_ipc_camera_pwn.py 10.0.0.1
```

I found this to be slightly buggy in my usage, my guess is this model does not always save the uploaded data properly. Performing it more than once may be necessary.
