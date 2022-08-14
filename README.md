This is a minimal proof of concept to remotely open a root shell on a Zyxel IP enabled camera. Known vulnerable models are

* Zyxel IPC-3605N
* Zyxel IPC-4605N

The IPC-2605N is also probably vulnerable, but I do not have one to test.

Usage requires python3.9 or newer

```
python3.9 ./zyxel_ipc_camera_pwn.py 10.0.0.1
```

Where `10.0.0.1` is replaced with IP or hostname of the camera you want to pwn. Running this script will add a telnet server listening on port 15555
that logs you in as root. The device reboots as part of the exploit process. You can then connect via telnet.
