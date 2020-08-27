# Ansible franklinkim.sudo role

[![Build Status](https://img.shields.io/travis/weareinteractive/ansible-sudo.svg)](https://travis-ci.org/weareinteractive/ansible-sudo)
[![Galaxy](http://img.shields.io/badge/galaxy-franklinkim.sudo-blue.svg)](https://galaxy.ansible.com/list#/roles/1380)
[![GitHub Tags](https://img.shields.io/github/tag/weareinteractive/ansible-sudo.svg)](https://github.com/weareinteractive/ansible-sudo)
[![GitHub Stars](https://img.shields.io/github/stars/weareinteractive/ansible-sudo.svg)](https://github.com/weareinteractive/ansible-sudo)

> `franklinkim.sudo` is an [Ansible](http://www.ansible.com) role which:
>
> * installs sudo
> * configures sudo

## Installation

Using `ansible-galaxy`:

```shell
$ ansible-galaxy install franklinkim.sudo
```

Using `requirements.yml`:

```yaml
- src: franklinkim.sudo
```

Using `git`:

```shell
$ git clone https://github.com/weareinteractive/ansible-sudo.git franklinkim.sudo
```

## Dependencies

* Ansible >= 1.9

## Variables

Here is a list of all the default variables for this role, which are also available in `defaults/main.yml`.

```yaml
---
# sudo_defaults:
#  - defaults: env_reset
#  - name: user1
#    defaults: requiretty
# sudo_users:
#  - name: '%group1'
#  - name: 'bar'
#    nopasswd: yes
#  - name: '%group2'
#    commands: '/bin/ls'
#

# package name (version)
sudo_package: sudo
# list of username or %groupname
sudo_users: []
# list of username or %groupname and their defaults
sudo_defaults: []
# default sudoers file
sudo_sudoers_file: ansible

```


## Usage

This is an example playbook:

```yaml
---

- hosts: all
  become: yes
  roles:
    - franklinkim.sudo
  vars:
    sudo_defaults:
      - defaults: env_reset
      - defaults: secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
      - name: 'user1'
        defaults: 'requiretty'
      - name: '%group1'
        defaults: '!requiretty'
    sudo_users:
      - name: 'user1'
      - name: 'user2'
        nopasswd: yes
      - name: '%group1'
        hosts: 127.0.0.1
      - name: '%group2'
        commands: '/bin/ls'
      - name: '%group3'
        users: 'user1,user2'
        groups: 'group1,group2'

```


## Testing

```shell
$ git clone https://github.com/weareinteractive/ansible-sudo.git
$ cd ansible-sudo
$ make test
```

## Contributing
In lieu of a formal style guide, take care to maintain the existing coding style. Add unit tests and examples for any new or changed functionality.

1. Fork it
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create new Pull Request

*Note: To update the `README.md` file please install and run `ansible-role`:*

```shell
$ gem install ansible-role
$ ansible-role docgen
```

## License
Copyright (c) We Are Interactive under the MIT license.
