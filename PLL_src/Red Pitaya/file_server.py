#file_server.py

#from time import sleep
import sys

import socket                   # Import socket module
port = int(sys.argv[2])         # Reserve a port for your service.
s = socket.socket()             # Create a socket object
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
host = '10.84.241.80'           # Get local machine name
s.bind((host, port))            # Bind to the port
s.listen(5)                     # Now wait for client connection.

print ('Server listening....')

filename=sys.argv[1]

while True:
    conn, addr = s.accept()     # Establish connection with client.
    print ('Got connection from' + str(addr))

    f = open(filename, 'rb')
    l = f.read(1024)
    while(l):
        conn.send(l)
        l= f.read(1024)
    f.close()
    conn.close()
