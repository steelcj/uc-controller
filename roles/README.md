# uc-controller/roles/README.md

## Description

This directory is used for testing and developing ansible roles

Once roles are fully tested and developed and fit they are added
to requirements.yml and installed into ~/.ansible/roles:

```bash
ansible-galaxy role install -r requirements.yml -p ~/.ansible/roles
```

Keep the `-p`: run from the repository, `ansible-galaxy` installs into the
first entry of `ansible.cfg`'s `roles_path`, which is this directory.
Roles are not linted or tested in uc-controller's own checks unless the work
is on them, so `.ansible-lint` leaves this directory out.
`tests/run_tests.py` offers to install a missing role, and fails on a role
installed at another version than its pin.

Then the roles are removed from the uc-controller/roles directory

