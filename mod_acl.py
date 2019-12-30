from multiprocessing import Pool
from functools import partial
from netmiko import ConnectHandler, NetMikoAuthenticationException, NetMikoTimeoutException
from yaml import safe_load
from pprint import pprint
from sys import argv
from json import dumps
from datetime import datetime

import getpass

def ssh_connect(hostname, device_type, username, password):

    device = {
        'device_type': device_type,
        'ip': hostname,
        'username': username,
        'password': password
    }

    return ConnectHandler(**device)


def get_valid_credentials(hostname, device_type):

    """
        gets username and password, opens an ssh session to verify the credentials
        then closes the ssh session

        returns username and password

        Doing this prevents multiple threads from locking out an account due to mistyped creds
    """

    # attempts to get the username, prompts if needed
    username = input('Username: ')

    # prompts user for password
    password = getpass.getpass()

    authenticated = False

    while not authenticated:

        try:

            test_ssh_session = ssh_connect(hostname, device_type, username, password)
            test_ssh_session.disconnect()

        except NetMikoAuthenticationException:

            print('authentication failed on ' + hostname + ' (CTRL + C to quit)')

            username = input('Username: ')
            password = getpass.getpass()

        except NetMikoTimeoutException:

            print('SSH timed out on ' + hostname)
            raise

        else:

            # if there is no exception set authenticated to true
            authenticated = True

    return username, password


def nxos_mod_acl(ssh_session, device, acl_name, acl_lines, append):

    """
        Updates ACLs on cisco_nxos devices
    """

    if not append:
        # remove the old ACL
        ssh_session.send_config_set('no ip access-list {}'.format(acl_name))

    # create the config set for the new ACL
    config_set = ['ip access-list {}'.format(acl_name)]
    config_set = config_set + acl_lines.splitlines()

    # command input on nexus devices is slow, so we use a delay_factor of 10 to slow down the input and prevent timeouts
    ssh_session.send_config_set(config_set, delay_factor = 10)

    result = ssh_session.send_command('show ip access-list {}'.format(acl_name))

    return result


def ios_mod_acl(ssh_session, device, acl_name, acl_lines, append, extended):

    """
        Updates ACLs on cisco_ios devices
    """

    if not append:
        # remove the old ACL
        if extended:
            ssh_session.send_config_set('no ip access-list extended {}'.format(acl_name))
        else:
            ssh_session.send_config_set('no ip access-list standard {}'.format(acl_name))

    # create the config set for the new ACL
    if extended:
        config_set = ['ip access-list extended {}'.format(acl_name)]
    else:
        config_set = ['ip access-list standard {}'.format(acl_name)]

    config_set = config_set + acl_lines.splitlines()

    ssh_session.send_config_set(config_set)

    result = ssh_session.send_command('show ip access-list {}'.format(acl_name))

    return result


def mod_acl(acl_name, acl_lines, append, extended, username, password, device):

    try:

        ssh_session = ssh_connect(device['hostname'], device['device_type'], username, password)

    except Exception as e:

        print('error {}'.format(device['hostname']))
        return {'device': device['hostname'], 'device_type': device['device_type'], 'result': e}


    try:

        if device['device_type'] == 'cisco_ios':

            result = ios_mod_acl(ssh_session, device, acl_name, acl_lines, append, extended)

        elif device['device_type'] == 'cisco_nxos':

            result = nxos_mod_acl(ssh_session, device, acl_name, acl_lines, append)

    except Exception as e:

        print('error {}'.format(device['hostname']))
        return {'device': device['hostname'], 'result': 'Failed\n{}'.format(e)}

    print('{} completed'.format(device['hostname']))

    return {'device': device['hostname'], 'device_type': device['device_type'], 'result': result}


def verify(acl_name, append):

    """
        Asks the user to verify settings in the YAML file
    """

    if append:

        mode = 'append'

    else:

        mode = 'replace'

    print('{} will be modified using mode {}'.format(acl_name, mode))

    user_input = input('Is this correct? [y/n] ').lower()

    if user_input[0] == 'y':

        return True

    else:

        return False


def validation(results):

    """
        Basic validation
        
        It's up to the user to read the results and verify consistancy between the length of ACLs on each device.

        If nexus_diff or ios_diff is True, then a difference was found between the number of lines for devices of that device type
    """

    validation_results = {'nexus': [], 'ios': [], 'nexus_diff': False, 'ios_diff': False}

    nexus_first_count = -1
    ios_first_count = -1

    for device in results:

        try:
            line_count = len(device['result'].splitlines())
        except AttributeError:
            line_count = 0

        result = {
            'hostname': device['device'],
            'device_type': device['device_type'],
            'result_lines': line_count
        }

        if device['device_type'] == 'cisco_nxos':
            
            if nexus_first_count == -1:
                nexus_first_count = line_count
            elif nexus_first_count != line_count:
                validation_results['nexus_diff'] = True

            validation_results['nexus'].append(result)
        elif device['device_type'] == 'cisco_ios':

            if ios_first_count == -1:
                ios_first_count = line_count
            elif ios_first_count != line_count:
                validation_results['ios_diff'] = True

            validation_results['ios'].append(result)

    return validation_results


def main():

    try:

        script_settings = safe_load(open(argv[1]))

    except IndexError:

        print('Please specify a configuration file')
        exit()


    # End the script if the settings are incorrect
    if not verify(script_settings['acl_name'], script_settings['append']):
        exit()

    # Get working credentials from the user
    username, password = get_valid_credentials(script_settings['device_list'][0]['hostname'], script_settings['device_list'][0]['device_type']) 

    # Spawn the number of threads configured in the YAML file
    with Pool(script_settings['threads']) as pool:

        results = pool.map(partial(mod_acl,
                         script_settings['acl_name'],
                         script_settings['acl_lines'],
                         script_settings['append'],
                         script_settings['extended'],
                         username,
                         password),
                 script_settings['device_list'])

    print('\nFULL RESULTS\n_________________')

    pprint(results)

    print('\nSUMMARY RESULTS\n_________________')
    validation_results = validation(results)

    pprint(validation_results)


main()
