# mod_acl

## Installation
* Clone the repository
`git clone --rescurse-submodules https://github.com/bjames/mod_acl`
* Initialize a new python virtual environment
`python -m virtualenv venv`
* Install the required python modules
`./venv/bin/python -m pip -r requirements.txt`

## Usage
* Create or modify one of the YAML files in the repo as needed (see examples folder)
* device_list entries should have a hostname and device_type (either cisco_ios or cisco_nxos)
```
    - hostname: 172.16.12.117
      device_type: cisco_ios
    - hostname: 172.16.12.116
      device_type: cisco_nxos
```
* acl_name should refer to an ACL that already exists
    * Creating new ACLs isn't currently supported, but will be added when needed
* if `append` is set to True, then the lines are added to the ACL. Otherwise the ACL is replaced
    * Line numbers can be specified in either instance, but should only be necessary when appending
    * When possible append False is preferred as this enforces consistancy
* Note on ACL lines the pipe prior to the list of ACEs must be present for the YAML to be parsed correctly
* Run the script with `./venv/bin/python mod_acl.py mod_acl.yml`