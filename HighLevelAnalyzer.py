# High Level Analyzer
# For more information and documentation, please go to https://github.com/saleae/logic2-examples

class Command:
    description = None
    address_count = None
    handler = None
    base_address = None

    def __init__(self, description, address_count=1, handler=None):
        self.description = description
        self.address_count = address_count
        self.handler = handler
    
    def set_base(self, base):
        self.base_address = base

    def handle(self, data):
        command_address = data[1]
        if self.handler is not None:
            return self.handler(data, self.base_address)
        if self.address_count == 1:
            return "{desc} ({hex})".format(desc = self.description, hex = hex(command_address))
        return "{desc}[{offset}] ({hex})".format(desc = self.description, hex = hex(command_address), offset = hex(command_address - self.base_address)[2:])

a = Command(description='hello')

command_table = {
    0x00: Command(description='Lower Column Start Address', address_count=16),
    0x10: Command(description='Upper Column Start Address', address_count=16),
    0x20: 'Set Memory Addressing Mode',
    0x21: 'Set Column Address',
    0x22: 'Set Page Address',
    0x40: Command(description='Set Display Start Line', address_count=2**6),
    0x81: 'Set Contrast Control',
    0x8D: 'Charge Pump Setting',
    0xA0: Command(description='Set segment re-map', address_count=2),
    0xA4: 'Entire Display On (follow RAM)',
    0xA5: 'Entire Display On (ignore RAM)',
    0xA6: 'Set Normal Display',
    0xA7: 'Set Inverse Display',
    0xA8: 'Set Multiplex Ratio',
    0xAE: 'Display Off',
    0xAF: 'Display On',
    0xB0: Command(description='Set Page Start Address', address_count=8),
    0xC0: 'Set COM Outpout Scan Direction (normal mode)',
    0xC8: 'Set COM Outpout Scan Direction (remapped mode)',
    0xD3: 'Set display offset',
    0xD5: 'Set Display Clock Divide Ratio',
    0xD9: 'Set pre-charge period',
    0xDA: 'Set COM Pins Hardware Configuration',
    0xDB: 'Set Vcomh Deselect Level',
}


print(type(command_table))

for key, value in command_table.items():
    print(key)
    print(value)
    if isinstance(value, Command):
        value.set_base(key)

def find_command(command_byte):
    if command_byte in command_table:
        return command_table[command_byte]
    for key, value in command_table.items():
        if not isinstance(value, Command):
            continue
        if command_byte < key:
            continue
        if command_byte >= key and command_byte < (value.address_count + key):
            return value
    return None

# byte 0 is 0x00.
def decode_command(data):
    command = find_command(data[1])
    if command is None:
        print("unknown command: {hex}".format(hex = hex(data[1])))
        return "({hex})".format(hex = hex(data[1]))
    if type(command) is str:
        return "{command} ({hex})".format(command = command, hex = hex(data[1]))
    if isinstance(command, Command):
        return command.handle(data)
    print("whoops")

I2C_ADDRESS_SETTING = 'I2C Address'
I2C_ADDRESSES = {
    '0x3C': 0x3c,
    '0x3d': 0x3d
}

class Transaction:
    is_multibyte_read: bool
    is_read: bool
    start_time: float
    end_time: float
    address: int
    data: bytearray

    def __init__(self, start_time):
        self.start_time = start_time
        self.data = bytearray()
        self.is_multibyte_read = False

class Hla():

    def __init__(self):
        '''
        Initialize this HLA.

        If you have any initialization to do before any methods are called, you can do it here.
        '''
        self.i2c_address = None
        self.current_transaction = None

    def get_capabilities(self):
        '''
        Return the settings that a user can set for this High Level Analyzer. The settings that a user selects will later be passed into `set_settings`.

        This method will be called first, before `set_settings` and `decode`
        '''

        return {
            'settings': {
                I2C_ADDRESS_SETTING: {
                    'type': 'choices',
                    'choices': ('0x3C', '0x3D')
                }
            }
        }

    def set_settings(self, settings):
        '''
        Handle the settings values chosen by the user, and return information about how to display the results that `decode` will return.

        This method will be called second, after `get_capbilities` and before `decode`.
        '''

        if I2C_ADDRESS_SETTING in settings:
            self.i2c_address = I2C_ADDRESSES[settings[I2C_ADDRESS_SETTING]]
            print("selected")
            print(self.i2c_address)

        # Here you can specify how output frames will be formatted in the Logic 2 UI
        # If no format is given for a type, a default formatting will be used
        # You can include the values from your frame data (as returned by `decode`) by wrapping their name in double braces, as shown below.
        return {
            'result_types': {
                'transaction': {
                    'format': '{{data.command}}'
                }
            }
        }

    def decode(self, frame):
        new_frame = None

        type = frame['type']
        if type == 'start':
            self.current_transaction = Transaction(frame['start_time'])
        elif type == 'stop' and self.current_transaction:
            transaction = self.current_transaction
            transaction.end_time = frame['end_time']
            new_frame = self.decode_transaction(transaction)
            self.current_transaction = None
            
        if self.current_transaction is not None:
            if type == 'address':
                address = frame['data']['address'][0]
                self.current_transaction.address = address >> 1
                self.current_transaction.is_read = (address & 0x01) == 1
            elif type == 'data':
                byte = frame['data']['data'][0]
                self.current_transaction.data.append(byte)
        if new_frame is not None:
            return new_frame
            
    def decode_transaction(self, transaction):

        if self.current_transaction.is_read:
            self.current_transaction = None
            return None

        return {
            'type': 'transaction',
            'start_time': transaction.start_time,
            'end_time': transaction.end_time,
            'data': {
                'DC': 'data' if transaction.data[0] & 0x40 else 'command',
                'command': decode_command(transaction.data) if transaction.data[0] == 0 else '',
                'address': transaction.address,
                'count': len(transaction.data),
                'data': str([str(x) for x in transaction.data]),
                'direction': 'read' if transaction.is_read else 'write'
            }
        }
        
