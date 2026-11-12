```bash
ssh-add -l                                              # is the key listed, and how?
ssh-add -d ~/.ssh/gradus-raw-initial-id_ed25519         # drop it
ssh-add ~/.ssh/gradus-raw-initial-id_ed25519            # re-add without -c
```



```bash
ssh -i ~/.ssh/gradus-raw-initial-id_ed25519 initial@10.119.134.207
```

1. **The real SSH key is in place.** Replace the placeholder in `inventories/onboard/dev/group_vars/all.yml` `authorized_keys` with your controller’s actual public key.
2. **`ex2-test` is running**, and `host_key_checking` is handled (play 5 SSHes to a fresh host).

Then the run:

~~~sh
# 0. rollback net
incus snapshot create ex2-test pre-onboard

# 1. roles (pulls steelcj.umask over SSH + the robertdebock roles)
ansible-galaxy install -r requirements.yml

# 2. confirm the raw group and vars resolve
ansible-inventory -i inventories/raw/incus.yml -i inventories/onboard/dev --graph

# output
@all:
  |--@ungrouped:
  |--@incus:
  |  |--@incus_local:
  |  |  |--@incus_local_default:
  |  |  |  |--ex2-test.default.local
  |--@raw:
  |  |--ex2-test.default.local
  |--@onboarded:


# 3. syntax check (now that roles are installed)
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  playbooks/lifecycle/10_onboard.yml --syntax-check

# output
playbook: playbooks/lifecycle/10_onboard.yml

# 4. Initial test
ANSIBLE_HOST_KEY_CHECKING=False \
ANSIBLE_STDOUT_CALLBACK=default \
ANSIBLE_CALLBACK_RESULT_FORMAT=yaml \
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  playbooks/lifecycle/10_onboard.yml -l 'ex2-test*' -vv

# 5. Add vars to ansible.cfg

```cfg
[defaults]
roles_path = ./roles:~/.ansible/roles:/usr/share/ansible/roles
inventory = ./inventories/raw
host_key_checking = False
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 3600
stdout_callback = default
callback_result_format = yaml
#stdout_callback = yaml
#callbacks_enabled = profile_tasks

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
```

then:
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev   playbooks/lifecycle/10_onboard.yml -l 'ex2-test*' -vv

error:

TASK [robertdebock.ntp : Install packages] ***************************************************************************************************************************
task path: /home/initial/areas/development/uc-controller/roles/robertdebock.ntp/tasks/main.yml:10
[DEPRECATION WARNING]: INJECT_FACTS_AS_VARS default to `True` is deprecated, top-level facts will not be auto injected after the change. This feature will be removed from ansible-core version 2.24.
Origin: /home/initial/areas/development/uc-controller/roles/robertdebock.ntp/vars/main.yml:17:15

15     - util-linux
16
17 ntp_packages: "{{ _ntp_packages[ansible_os_family ~ '-' ~ ansible_distribution_major_version] | default(_ntp_packa...
                 ^ column 15

Use `ansible_facts["fact_name"]` (no `ansible_` prefix) instead.

[ERROR]: Task failed: Module failed: No package matching 'ntp' is available
Origin: /home/initial/areas/development/uc-controller/roles/robertdebock.ntp/tasks/main.yml:10:3

 8   delegate_to: localhost
 9
10 - name: Install packages
     ^ column 3

fatal: [ex2-test.default.local]: FAILED! => 
    changed: false
    msg: No package matching 'ntp' is available

PLAY RECAP ***********************************************************************************************************************************************************
ex2-test.default.local     : ok=70   changed=13   unreachable=0    failed=1    skipped=23   rescued=0    ignored=0   



# 4. first first
ANSIBLE_HOST_KEY_CHECKING=False \
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  playbooks/lifecycle/10_onboard.yml -l 'ex2-test*' -vv


  
# 4. first clean test
ANSIBLE_HOST_KEY_CHECKING=False \
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  playbooks/lifecycle/10_onboard.yml -l ex2-test -vv

# 4. the run, one host, verbose
ANSIBLE_HOST_KEY_CHECKING=False \
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  playbooks/lifecycle/10_onboard.yml -l ex2-test -e target_group=webservers -vv



~~~





Watch the play boundaries: umask (login.defs/profile.d, no visible drama), bootstrap (installs python3 + sudo via raw), baseline (the long one), then the switch-to-initial and the final SSH-as-initial confirmation. Play 5 reporting `id` as `initial` with sudo is your pass line.

Verify after:

```sh
incus exec ex2-test -- grep -E '^(UMASK|HOME_MODE)' /etc/login.defs   # 0027 / 0750
incus exec ex2-test -- stat -c '%a %n' /home/initial                   # expect 750
incus exec ex2-test -- id initial
ssh initial@$(incus list ex2-test -c4 --format csv | cut -d' ' -f1) id
```

Reset and rerun as needed with `incus snapshot restore ex2-test pre-onboard`.

Run it and paste what you get, especially the first failure if one shows. Given the moving parts (fork push, the key, the connection switch), I’d expect one or two things to need a nudge on the first pass, and the `-vv` output will tell us exactly where.