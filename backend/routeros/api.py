# Author: Arturs Laizans

import socket
import ssl
import hashlib
import binascii

# Constants - Define defaults
PORT = 8728
SSL_PORT = 8729

USER = ''
PASSWORD = ''

USE_SSL = False

VERBOSE = False  # Whether to print API conversation width the router. Useful for debugging
VERBOSE_LOGIC = 'OR'  # Whether to print and save verbose log to file. AND - print and save, OR - do only one.
VERBOSE_FILE_MODE = 'w'  # Weather to create new file ('w') for log or append to old one ('a').



class LoginError(Exception):
    pass


class WordTooLong(Exception):
    pass


class CreateSocketError(Exception):
    pass


class Api:

    def __init__(self, address, logger, user=USER, password=PASSWORD, use_ssl=USE_SSL, port=False):

        self.successful = False
        self.address = address
        self.user = user
        self.password = password
        self.use_ssl = use_ssl
        self.port = port

        # Port setting logic
        if port:
            self.port = port
        elif use_ssl:
            self.port = SSL_PORT
        else:
            self.port = PORT

        # Create Log instance to save or print verbose logs
        self.log = logger
        self.log.info('')
        self.log.info('#-----------------------------------------------#')
        self.log.info('API IP - {}, USER - {}'.format(address, user))

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.sock.settimeout(5)  # Set socket timeout to 5 seconds
        self.connection = None
        self.open_socket()
        self.login()
        self.log.info('Instance of Api created')

    # Open socket connection with router and wrap with SSL is needed.
    def open_socket(self):

        try:
            # Trying to connect to RouterOS, error can occur if IP address is not reachable, or API is blocked in
            # RouterOS firewall or ip services, or port is wrong.
            self.connection = self.sock.connect((self.address, self.port))

        except OSError:
            raise CreateSocketError('Error: API failed to connect to socket. Host: {}, port: {}.'.format(self.address,
                                                                                                         self.port))

        self.log.info('API socket connection opened.')

    # Login API connection into RouterOS
    def login(self):
        sentence = ['/login', '=name=' + self.user, '=password=' + self.password]
        reply = self.communicate(sentence)
        if len(reply[0]) == 1 and reply[0][0] == '!done':
            # If login process was successful
            self.log.info('Logged in successfully!')
            self.successful = True
            return reply
        elif 'Error' in reply:
            # Else if there was some kind of error during login process
            self.log.info('Error in login process - {}'.format(reply))
            raise LoginError('Login ' + reply)
        elif len(reply[0]) == 2 and reply[0][1][0:5] == '=ret=':
            # Else if RouterOS uses old API login method, code continues with old method
            self.log.info('Using old login process.')
            md5 = hashlib.md5(('\x00' + self.password).encode('utf-8'))
            md5.update(binascii.unhexlify(reply[0][1][5:]))
            sentence = ['/login', '=name=' + self.user, '=response=00'
                        + binascii.hexlify(md5.digest()).decode('utf-8')]
            self.log.info('Logged in successfully!')
            self.successful = True
            return self.communicate(sentence)

    # Sending data to router and expecting something back
    def communicate(self, sentence):

        # There is specific way of sending word length in RouterOS API.
        # See RouterOS API Wiki for more info.
        def send_length(w):
            length_to_send = len(w)
            if length_to_send < 0x80:
                num_of_bytes = 1  # For words smaller than 128
            elif length_to_send < 0x4000:
                length_to_send += 0x8000
                num_of_bytes = 2  # For words smaller than 16384
            elif length_to_send < 0x200000:
                length_to_send += 0xC00000
                num_of_bytes = 3  # For words smaller than 2097152
            elif length_to_send < 0x10000000:
                length_to_send += 0xE0000000
                num_of_bytes = 4  # For words smaller than 268435456
            elif length_to_send < 0x100000000:
                num_of_bytes = 4  # For words smaller than 4294967296
                self.sock.sendall(b'\xF0')
            else:
                raise WordTooLong('Word is too long. Max length of word is 4294967295.')
            self.sock.sendall(length_to_send.to_bytes(num_of_bytes, byteorder='big'))

            # Actually I haven't successfully sent words larger than approx. 65520.
            # Probably it is some RouterOS limitation of 2^16.

        # The same logic applies for receiving word length from RouterOS side.
        # See RouterOS API Wiki for more info.
        def receive_length():
            r = self.sock.recv(1)  # Receive the first byte of word length

            # If the first byte of word is smaller than 80 (base 16),
            # then we already received the whole length and can return it.
            # Otherwise if it is larger, then word size is encoded in multiple bytes and we must receive them all to
            # get the whole word size.

            if r < b'\x80':
                r = int.from_bytes(r, byteorder='big')
            elif r < b'\xc0':
                r += self.sock.recv(1)
                r = int.from_bytes(r, byteorder='big')
                r -= 0x8000
            elif r < b'\xe0':
                r += self.sock.recv(2)
                r = int.from_bytes(r, byteorder='big')
                r -= 0xC00000
            elif r < b'\xf0':
                r += self.sock.recv(3)
                r = int.from_bytes(r, byteorder='big')
                r -= 0xE0000000
            elif r == b'\xf0':
                r = self.sock.recv(4)
                r = int.from_bytes(r, byteorder='big')

            return r

        def read_sentence():
            rcv_sentence = []  # Words will be appended here
            rcv_length = receive_length()  # Get the size of the word

            trap = False  # This variable will change if there is !trap error occurred
            while rcv_length != 0:
                received = b''
                while rcv_length > len(received):
                    rec = self.sock.recv(rcv_length - len(received))
                    if rec == b'':
                        raise RuntimeError('socket connection broken')
                    rec = rec
                    received += rec
                received = received.decode('utf-8')
                self.log.info('<<< {}'.format(received))
                if trap:  # If !trap (error) in previous word return what was the error
                    return 'Error: Host: {}, RouterOS API replied: {}'.format(self.address, received.split('=')[2])
                if received == '!trap':  # Some error occurred
                    trap = True
                rcv_sentence.append(received)
                rcv_length = receive_length()  # Get the size of the next word
            self.log.info('')
            return rcv_sentence

        # Sending part of conversation

        # Each word must be sent separately.
        # First, length of the word must be sent,
        # Then, the word itself.
        for word in sentence:
            send_length(word)
            self.sock.sendall(word.encode('utf-8'))  # Sending the word
            self.log.info('>>> {}'.format(word))
        self.sock.sendall(b'\x00')  # Send zero length word to mark end of the sentence
        self.log.info('')

        # Receiving part of the conversation

        # Will continue receiving until receives '!done' or some kind of error.
        # Everything will be appended to paragraph variable, and then returned.
        paragraph = []
        while sentence[0] != '!done':
            sentence = read_sentence()
            if 'Error' in sentence:
                return sentence
            paragraph.append(sentence)
        return paragraph

    # Initiate a conversation with the router
    def talk(self, message):

        # It is possible for message to be string, tuple or list containing multiple strings or tuples
        if type(message) == str or type(message) == tuple:
            return self.send(message)
        elif type(message) == list:
            reply = []
            for sentence in message:
                reply.append(self.send(sentence))
            return reply
        else:
            raise TypeError('talk() argument must be str or tuple containing str or list containing str or tuples')

    def send(self, sentence):
        # If sentence is string, not tuples of strings, it must be divided in words
        if type(sentence) == str:
            sentence = sentence.split()
        reply = self.communicate(sentence)
        print("reply : ", reply)
        if 'Error' in reply:
            return reply

        # reply is list containing strings with RAW output form API
        # nice_reply is a list containing output form API sorted in dictionary for easier use later
        nice_reply = []
        for m in range(len(reply) - 1):
            nice_reply.append({})
            for k, v in (x[1:].split('=') for x in reply[m][1:]):
                nice_reply[m][k] = v
        return nice_reply

    def close(self):
        self.sock.close()
