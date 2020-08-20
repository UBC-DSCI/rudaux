UNAME := $(shell uname | tr '[:upper:]' '[:lower:]')
ARCH := $(shell uname -m)
TOP := $(shell pwd)
TF_PATH := $(TOP)/../terraform

export PATH := $(TF_PATH)/bin/$(UNAME)_$(ARCH):$(PATH)

#ANSIBLE_CMD  = TF_STATE=$(TF_PATH)/$(ENV) ansible --private-key=../keys/id_syzygy_stat -i ./inventory
#PLAYBOOK_CMD = TF_STATE=$(TF_PATH)/$(ENV) ansible-playbook --private-key=../keys/id_syzygy_stat -i ./inventory
ANSIBLE_CMD  = TF_STATE=$(TF_PATH)/$(ENV) ansible --private-key=~/.ssh/id_rsa -i ./inventory
PLAYBOOK_CMD = TF_STATE=$(TF_PATH)/$(ENV) ansible-playbook --private-key=~/.ssh/id_rsa -i ./inventory

help: tasks

tasks: 
	@grep -A1 ^HELP Makefile | sed -e ':begin;$$!N;s/HELP: \(.*\)\n\(.*:\).*/\2 \1/;tbegin;P;D' | grep -v \\\-\\\- | sort | awk -F: '{printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


check-playbook:
ifndef PLAYBOOK
	$(error PLAYBOOK is not defined [PLAYBOOK=])
else
export _PLAYBOOK = plays/$(PLAYBOOK).yml
endif

check-env:
ifndef ENV
	$(error environment is not defined [ENV=])
endif

check-limit:
ifndef LIMIT
export _LIMIT = --limit all
else
export _LIMIT = --limit $(LIMIT)
endif

HELP: Lists plays
list-playbooks:
	@grep -RH ^## plays/ | sed -e 's/\(plays\/\)\(.*\)\(.yml\)/\2/' | sort | awk 'BEGIN {FS = ":## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


HELP: Lists the tasks in a $PLAYBOOK in $ENV
list-tasks: check-playbook check-limit
	$(PLAYBOOK_CMD) --list-tasks $(_LIMIT) $(_PLAYBOOK)

HELP: Lists all hosts in $ENV
hosts: check-env check-limit
	$(ANSIBLE_CMD) --list-hosts $(_LIMIT) all

HELP: Run $PLAYBOOK ON $ENV in check-mode
playbook/check: check-env check-playbook check-limit
	$(PLAYBOOK_CMD) --check --diff $(_LIMIT) $(_PLAYBOOK)

HELP: Run $PLAYBOOK ON $ENV
playbook: check-env check-playbook check-limit
	$(PLAYBOOK_CMD) $(_LIMIT) $(_PLAYBOOK)

HELP: Setup ansible and refresh external roles
ansible/setup: check-env check-limit
	$(ANSIBLE_CMD) -m setup all
	/bin/bash scripts/role_module_update.sh

