```bash
INFO     default ➜ discovery: scenario test matrix: dependency, destroy, syntax, create, prepare, converge, idempotence, verify, destroy
INFO     default ➜ prerun: Performing prerun with role_name_check=0...
INFO     default ➜ dependency: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-galaxy install
  │   --role-file /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/requirements.yml
  │ 
  │ Starting galaxy collection install process
  │ Nothing to do. All requested collections are already installed. If you want to reinstall them, consider using `--force`.
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ dependency: Dependency completed successfully.
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-galaxy collection
  │   install
  │   --requirements-file requirements.yml
  │ 
  │ Skipping install, no requirements found
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ dependency: Dependency completed successfully.
INFO     default ➜ dependency: Executed: Successful
INFO     default ➜ destroy: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest
  │   /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/destroy.yml
  │ 
  │ 
  │ PLAY [Destroy] *****************************************************************
  │ 
  │ TASK [Delete the instances] ****************************************************
  │ ok: [localhost] => (item=foomuuri-debian13)
  │ 
  │ TASK [Empty the instance config] ***********************************************
  │ changed: [localhost]
  │ 
  │ PLAY RECAP *********************************************************************
  │ localhost                  : ok=2    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
  │ 
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ destroy: Executed: Successful
INFO     default ➜ syntax: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest
  │   --syntax-check /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/converge.yml
  │ 
  │ 
  │ playbook: /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/converge.yml
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ syntax: Executed: Successful
INFO     default ➜ create: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest
  │   /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/create.yml
  │ 
  │ 
  │ PLAY [Create] ******************************************************************
  │ 
  │ TASK [Find existing instances] *************************************************
  │ ok: [localhost] => (item=foomuuri-debian13)
  │ 
  │ TASK [Launch the instances] ****************************************************
  │ changed: [localhost] => (item=foomuuri-debian13)
  │ 
  │ TASK [Wait for systemd in the instances] ***************************************
  │ ok: [localhost] => (item=foomuuri-debian13)
  │ 
  │ TASK [Write the instance config] ***********************************************
  │ changed: [localhost]
  │ 
  │ PLAY RECAP *********************************************************************
  │ localhost                  : ok=4    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
  │ 
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ create: Executed: Successful
INFO     default ➜ prepare: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest
  │   /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/prepare.yml
  │ 
  │ 
  │ PLAY [Prepare] *****************************************************************
  │ 
  │ TASK [Install Python and sudo] *************************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ PLAY RECAP *********************************************************************
  │ foomuuri-debian13          : ok=1    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
  │ 
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ prepare: Executed: Successful
INFO     default ➜ converge: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest
  │   /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/converge.yml
  │ 
  │ 
  │ PLAY [Converge] ****************************************************************
  │ 
  │ TASK [Gathering Facts] *********************************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_ssh_port is set correctly] ***********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_ssh_sources is set correctly] ********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_services is set correctly] ***********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if each item in foomuuri_services is set correctly] ***
  │ ok: [foomuuri-debian13 -> localhost] => (item=https)
  │ ok: [foomuuri-debian13 -> localhost] => (item=1337)
  │ ok: [foomuuri-debian13 -> localhost] => (item=5353)
  │ ok: [foomuuri-debian13 -> localhost] => (item=http)
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_default_protocol is set correctly] ***
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_base_services is set correctly] ******
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_outgoing is set correctly] ***********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_fragment and foomuuri_base_fragment are set correctly] ***
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_purge is set correctly] **************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if SSH is accepted when foomuuri_require_ssh is set] ***
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if the mappings are set correctly] ***************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if each iplist name starts with @] ***************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if each item in foomuuri_files is set correctly] ***
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if no value holds a line break] ******************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if no rule value holds a brace] ******************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Remove conflicting software] **************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Install required software] ****************************
  │ changed: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Read the installed Foomuuri version] ******************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if the installed Foomuuri is recent enough] ******
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Mask nftables.service] ********************************
  │ changed: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Place the fragment] ***********************************
  │ changed: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Remove the fragment] **********************************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Place extra files] ************************************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Remove extra files] ***********************************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Find configuration files] *****************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Remove unmanaged configuration files] *****************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Check the configuration] ******************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Start and enable foomuuri] ****************************
  │ changed: [foomuuri-debian13]
  │ 
  │ RUNNING HANDLER [steelcj.foomuuri : Reload foomuuri] ***************************
  │ changed: [foomuuri-debian13]
  │ 
  │ PLAY RECAP *********************************************************************
  │ foomuuri-debian13          : ok=24   changed=5    unreachable=0    failed=0    skipped=6    rescued=0    ignored=0
  │ 
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ converge: Executed: Successful
INFO     default ➜ idempotence: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest,molecule-idempotence-notest
  │   /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/converge.yml
  │ 
  │ 
  │ PLAY [Converge] ****************************************************************
  │ 
  │ TASK [Gathering Facts] *********************************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_ssh_port is set correctly] ***********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_ssh_sources is set correctly] ********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_services is set correctly] ***********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if each item in foomuuri_services is set correctly] ***
  │ ok: [foomuuri-debian13 -> localhost] => (item=https)
  │ ok: [foomuuri-debian13 -> localhost] => (item=1337)
  │ ok: [foomuuri-debian13 -> localhost] => (item=5353)
  │ ok: [foomuuri-debian13 -> localhost] => (item=http)
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_default_protocol is set correctly] ***
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_base_services is set correctly] ******
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_outgoing is set correctly] ***********
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_fragment and foomuuri_base_fragment are set correctly] ***
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if foomuuri_purge is set correctly] **************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if SSH is accepted when foomuuri_require_ssh is set] ***
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if the mappings are set correctly] ***************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if each iplist name starts with @] ***************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if each item in foomuuri_files is set correctly] ***
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if no value holds a line break] ******************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Test if no rule value holds a brace] ******************
  │ ok: [foomuuri-debian13 -> localhost]
  │ 
  │ TASK [steelcj.foomuuri : Remove conflicting software] **************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Install required software] ****************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Read the installed Foomuuri version] ******************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Test if the installed Foomuuri is recent enough] ******
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Mask nftables.service] ********************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Place the fragment] ***********************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Remove the fragment] **********************************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Place extra files] ************************************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Remove extra files] ***********************************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Find configuration files] *****************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Remove unmanaged configuration files] *****************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Check the configuration] ******************************
  │ skipping: [foomuuri-debian13]
  │ 
  │ TASK [steelcj.foomuuri : Start and enable foomuuri] ****************************
  │ ok: [foomuuri-debian13]
  │ 
  │ PLAY RECAP *********************************************************************
  │ foomuuri-debian13          : ok=22   changed=0    unreachable=0    failed=0    skipped=7    rescued=0    ignored=0
  │ 
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ idempotence: Executed: Successful
INFO     default ➜ verify: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest
  │   /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/verify.yml
  │ 
  │ 
  │ PLAY [Verify] ******************************************************************
  │ 
  │ TASK [Read the fragment] *******************************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Test if the fragment holds the calculated rules] *************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Read the installed Foomuuri version] *************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Test if the public zone matches the installed version] *******************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Check the configuration] *************************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Read the state of the services] ******************************************
  │ ok: [foomuuri-debian13] => (item=foomuuri.service)
  │ ok: [foomuuri-debian13] => (item=nftables.service)
  │ 
  │ TASK [Test if foomuuri is active and enabled, and nftables.service is masked] ***
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [List the nftables tables] ************************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Test if Foomuuri's table is the only one] ********************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Read the loaded ruleset] *************************************************
  │ ok: [foomuuri-debian13]
  │ 
  │ TASK [Test if the SSH port is in the loaded ruleset] ***************************
  │ ok: [foomuuri-debian13]
  │ 
  │ PLAY RECAP *********************************************************************
  │ foomuuri-debian13          : ok=11   changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
  │ 
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ verify: Executed: Successful
INFO     default ➜ destroy: Executing
  ┌──────────────────────────────────────────────────────────────────────────────────
  │ ansible-playbook --inventory /home/initial/.ansible/tmp/molecule.SbqZ.default/inventory
  │   --skip-tags molecule-notest,notest
  │   /home/initial/areas/development/tmp/ansible-role-foomuuri/molecule/default/destroy.yml
  │ 
  │ 
  │ PLAY [Destroy] *****************************************************************
  │ 
  │ TASK [Delete the instances] ****************************************************
  │ changed: [localhost] => (item=foomuuri-debian13)
  │ 
  │ TASK [Empty the instance config] ***********************************************
  │ changed: [localhost]
  │ 
  │ PLAY RECAP *********************************************************************
  │ localhost                  : ok=2    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
  │ 
  └─ Return code: 0 ─────────────────────────────────────────────────────────────────
INFO     default ➜ destroy: Executed: Successful
INFO     default ➜ scenario: Pruning extra files from scenario ephemeral directory
INFO     Molecule executed 1 scenario (1 successful)

DETAILS                                                                        
default ➜ dependency: Executed: Successful
default ➜ destroy: Executed: Successful
default ➜ syntax: Executed: Successful
default ➜ create: Executed: Successful
default ➜ prepare: Executed: Successful
default ➜ converge: Executed: Successful
default ➜ idempotence: Executed: Successful
default ➜ verify: Executed: Successful
default ➜ destroy: Executed: Successful

SCENARIO RECAP                                                                 
default                   : actions=9  successful=8  disabled=0  skipped=0  missing=0  failed=0

```

