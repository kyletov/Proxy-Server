import sys
import os
import time
import socket
import select

_port = 8888
_hostname = "localhost"
_max_msg_size = 256


def setup_server(hostname, port):
    '''Return a server socket bound to the specified port.'''
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    connection.setblocking(0)
    connection.bind((hostname, port))
    connection.listen(5)
    return connection

def handle_message(sock, sockets):
    '''Process the message sent on socket sock and then return a list of client 
    sockets that have been terminated.'''

    to_remove = []
    msg = sock.recv(_max_msg_size).decode("UTF-8")
    if len(msg.strip()) == 0:
        return [sock]

    firstfield = msg.strip().split()[0]
    if len(firstfield) == 0 or \
       (sockets[sock][1] == None and firstfield != "/user"):
        to_remove.append(sock)

    return to_remove


def parse_header(request):
    '''Parse the headers for usable bits (method (i.e. GET), host, and file path)
    '''
    headers = request.split('\n')
    top_header = headers[0].split()
    method = top_header[0]
    filename = top_header[1]
    return top_header, method, filename

def fetch_from_cache(filename):
    '''if the file exists within our cache folder, we fetch it and return it
    to main to be redirected to the client. If a timeout arg is inputted, we
    implement the expiry of the cache files as well.'''
    filename = filename[0] + filename[1:].replace("/", "-")
    
    time_until_expire = None
    if len(sys.argv) == 2:
        time_until_expire = int(sys.argv[1])

    try:
        if os.path.exists("cache"):
            if time_until_expire:
                last_mod = os.path.getmtime('cache' + filename)
                expiration_time = last_mod + time_until_expire
                if (expiration_time <= time.time()):
                    return None
            file_input = open('cache' + filename, 'rb')
            content = file_input.read()
            file_input.close()
            return content
    except:
        return None
    
def save_in_cache(filename, content):
    '''If a cache directory does not exist, then we create it.

    We also check for a text document (e.g. .html) and adjust the Content Length
    attribute to suit with our modified injected html code (the yellow banner)

    We finally save the encoded data into a binary file in the cache directory'''
    
    if not os.path.exists("cache"):
        os.mkdir('cache')
        os.chmod('cache', 0o711)

    #if we find a text file (e.g. .html)
    if filename[-5:] == '.html' or filename[-4:] == '.php' or filename[-1] == '/':

        #indexing for the content-length
        string_content = content.decode("UTF-8")

        #swapping the banners
        fresh = '<p style="z-index:9999; position:fixed; top:20px; left:20px; width:200px; height:100px; background-color:yellow; padding:10px; font-weight:bold;">FRESH VERSION AT: '
        cached = '<p style="z-index:9999; position:fixed; top:20px; left:20px; width:200px; height:100px; background-color:yellow; padding:10px; font-weight:bold;">CACHED VERSION AS OF: '
        fresh_index = string_content.find(fresh)
        string_content = string_content[:fresh_index] + cached + string_content[fresh_index+len(cached):]

        #comparing the number of characters between old and new banner
        fresh_len = len(str(fresh))
        cached_len = len(str(cached))

        #string_content = content.decode("UTF-8")#indexing for the content-length
        index = string_content.find('Content-Length: ') + 16
        content_n_len = 0
        for i in string_content[index:]:#finding the number of digits in new banner
            if i.isdigit():
                content_n_len += 1
            else:
                break

        #getting the number
        content_n = int(content[index:index+content_n_len])
        length_without_digits = content_n - fresh_len + cached_len - content_n_len

        #converting the number into a string (also taking into account addition/removal of an extra digit)
        str_new_length = str(length_without_digits)
        length_without_digits += len(str_new_length)

        #makes inserting easier since we couldn't get .replace() to work well
        old_length = 'Content-Length: ' + str(content_n)
        new_length = 'Content-Length: ' + str(length_without_digits)

        #replaceing content-length
        index_content_len = string_content.find(old_length)
        string_content = string_content[:index_content_len] + new_length + string_content[index_content_len+len(new_length):]            

        #re-encoding to be written as a binary file in cache
        content = string_content.encode("UTF-8")

    # Cache-saving naming convention.
    filename = filename[0] + filename[1:].replace("/", "-")
    file_to_save = open('cache' + filename, 'wb')
    file_to_save.write(content)
    file_to_save.close()

def fetch_from_server(filename):
    '''If directed to a root directory, we first add on the /index.html file
    extension. Afterwords, we make a socket connection to the right web server,
    forward the client's request, and retrieve the requested file, which then
    goes to be saved into cache.

    We also check for a text document (e.g. .html) and change the Content Length
    attribute while injecting our html code (the yellow banner)'''
    try:
        if filename[-1] == '/':
            filename = filename + "index.html"
        filename_split = filename.split('/')
        if len(filename_split) == 2:
            filename_split.append("index.html")
        host = filename_split[1]
        file_path = ""
        for subfile in filename_split[2:]:
            if subfile == "":
                break
            else:
                file_path = file_path + "/" + subfile

        # Create socket to webbrowser
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, 80))
        get_request = "GET {0} HTTP/1.1\r\nHost: {1}\r\n\r\n".format(file_path, host)
        sock.sendall(get_request.encode("UTF-8"))

        content = b""
        while True:
            data = sock.recv(_max_msg_size)
            if not data:
                break
            content = content + data
        sock.close()

        #if we find a text file (e.g. .html)
        if filename[-5:] == '.html' or filename[-4:] == '.php':
            end_of_body = content.find(b'<body>')
            text = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            html_tag = b'<p style="z-index:9999; position:fixed; top:20px; left:20px; width:200px; height:100px; background-color:yellow; padding:10px; font-weight:bold;">FRESH VERSION AT: </p>\n'
            end_of_p = html_tag.find(b'</p>')
            inject_html = html_tag[:end_of_p] + text.encode("UTF-8") + html_tag[end_of_p:]
            content_begin = content[:end_of_body+len(b'<body>\n')] + inject_html
            content_end = content[end_of_body+len(b'<body>\n'):]
            content = content_begin + content_end

            string_content = content.decode("UTF-8") #indexing for the content-length
            index = string_content.find('Content-Length: ') + 16
            content_n_len = 0
            for i in string_content[index:]: #finding the number of digits
                if i.isdigit():
                    content_n_len += 1
                else:
                    break

            #getting the number
            content_n = int(content[index:index+content_n_len])
            html_len = len(inject_html)
            length_without_digits = content_n + html_len - content_n_len

            #converting the number into a string (also taking into account addition/removal of an extra digit)
            str_new_length = str(length_without_digits)
            length_without_digits += len(str_new_length)

            #makes inserting easier since we couldn't get .replace() to work well
            old_length = 'Content-Length: ' + str(content_n)
            new_length = 'Content-Length: ' + str(length_without_digits)

            #replaceing content-length
            index_content_len = string_content.find(old_length)
            string_content = string_content[:index_content_len] + new_length + string_content[index_content_len+len(new_length):]            

            #re-encoding to be sent to web server
            content = string_content.encode("UTF-8")
            

        return content
    except:
        print(sys.exc_info()[0])
        print("Something broke")
        return None
    
def fetch_file(filename):
    '''check cache first if file exists. If it does, get it from there.
    Otherwise, we send a request to the web server.'''
    file_from_cache = fetch_from_cache(filename)

    if file_from_cache:
        print('Retrieved from cache')
        return file_from_cache
    else:
        file_from_server = fetch_from_server(filename)
        if file_from_server:
            print('Retrieved from server')
            save_in_cache(filename, file_from_server)
            return file_from_server
        else:
            return None

if __name__ == "__main__":
    '''We listen for new connections, talk to existing ones, and kill off
    terminated ones. Select is also implemented so requests do not get mixed
    up between multiple clients.'''
    connection = setup_server(_hostname, _port)

    inputs = [connection]
    clients = {}
    while 1:
        '''Infinite loop to persistently communicate to existing sockets and
        listen for new ones'''
 
        inps, outs, errors = select.select(inputs, [], [])

        for inp in inps:
            if inp == connection: # New connection
                (client, address) = connection.accept()
                clients[client] = (address, None)
                inputs.append(client)
                print("Accepted new client", address)
                msg = b''
                while True:
                    client_msg = client.recv(_max_msg_size)
                    msg = msg + client_msg
                    if not client_msg or b'\r\n\r\n' in client_msg:
                        break
                msg = msg.decode("UTF-8")
                if msg == '':
                    break
                header = msg.replace('gzip', 'identity')
                top_header, method, filename = parse_header(header)
                if filename == '/':
                    filename = filename + 'index.html'
                content = fetch_file(filename)
                if not content:
                    content = b'HTTP/1.1 404 NOT FOUND\r\n File Not Found'
                client.sendall(content)
            else:
                try:
                    to_remove = handle_message(inp, clients)
                except socket.error:
                    to_remove = [inp]
                for client in to_remove:
                    print("Dropping client", clients[client])
                    del clients[client]
                    inputs.remove(client) 
                    client.close()

    print("Terminating")
    connection.close()

