import socket, json
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.sendto(json.dumps({"cmd":"set_control_mode","mode":"Trajectory"}).encode(), ("127.0.0.1",5065))
s.sendto(json.dumps({"cmd":"set_trajectory","mode":"Circle","speed":6.0,"circle_radius":12.0,"loop":True,"reset":True}).encode(), ("127.0.0.1",5065))
s.close()
print("sent")
