## Setup Ansible venvs

You can create one or more ansible python venvs and switch the current venv using `scipts/make_ansible_venv.py`

### make_ansible_venv.py

```bash
python3 scripts/make_ansible_venv.py --help
```

#### Install ansible to venv

This command installs the latest stable version of ansible and makes it the current ansible:

```bash
python3 scripts/make_ansible_venv.py latest
```

Output example:

```bash
Latest stable ansible is 14.6.0
Already present: /home/initial/.venvs/ansible/14.6.0/ansible
Current is now 14.6.0
ansible 14.6.0 [core 2.21.6]
Activate with: . /home/initial/.venvs/ansible/current/bin/activate
```

After activating you will have your vevns prompt will show the current version:

```bash
(ansible-14.5.0) initial@flow:~/areas/development/uc-controller$ . /home/initial/.venvs/ansible/current/bin/activate
(ansible-14.6.0) initial@flow:~/areas/development/uc-controller$ 
```

So we bumped the version from 14.5.0 to 14.6.0. If we want to switch to the old version we can run the following to make it the current version:

```bash
python3 scripts/make_ansible_venv.py 14.5.0
```

or we manually activate version 14.5.0 by running the following leaving 14.6.0 as the current ansible

```bash
. /home/initial/.venvs/ansible/14.5.0/ansible/bin/activate
```

#### Confirm versions

```bash
ansible-community --version
```

Output:

```bash
Ansible community version 14.6.0
```

```bash
ansible --version
```

Output example:

```bash
ansible [core 2.21.6]
  config file = /home/initial/areas/development/uc-controller/ansible.cfg
  configured module search path = ['/home/initial/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /home/initial/.venvs/ansible/14.6.0/ansible/lib/python3.12/site-packages/ansible
  ansible collection location = /home/initial/.ansible/collections:/usr/share/ansible/collections
  executable location = /home/initial/.venvs/ansible/14.6.0/ansible/bin/ansible
  python version = 3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0] (/home/initial/.venvs/ansible/14.6.0/ansible/bin/python)
  jinja version = 3.1.6
  pyyaml version = 6.0.3 (with libyaml v0.2.5)
```



