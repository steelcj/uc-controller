I'd put them in different places, because they do different jobs.

**`plain-vault-batch-passwords.md` fits the controller docs**, if it's the process for generating and loading vault passwords in batches. It describes how the controller handles secrets, so it belongs next to the Ansible inventory, vault layout and playbook docs it relies on.

**The Diceware live USB setup is a poor fit there.** The kit is built to be independent of the controller, and the passphrases it makes protect things above the controller: your password manager master password, disk encryption, and probably the vault password itself. Filing its procedure inside the controller docs creates a circular dependency. When you most need the procedure (rebuilding, recovering, or rotating after a compromise), the controller is the thing that might be missing or untrusted.

A layout that respects that:

- **The Diceware doc and the `dw` script in a small standalone archive**, something like `security-procedures` or `offline-secrets` (in SAT terms, its own archive in `en-ca`). Version the script there as the source of truth. The DWTOOLS stick is then just a copy of it.
- **The controller docs link to it.** The vault batch doc can say "vault passwords are generated with the offline Diceware kit, see …" without owning the procedure.
- **A printed copy goes in the kit**, stored with the sticks and dice, so you can follow the procedure with no working computer beyond the kit itself.

Whichever location you choose:

- **No secrets in either doc:** no example passphrases that were actually used, and no vault password hints.
- **Checksum stored separately:** keep the wordlist checksum you recorded out of the repo that holds the procedure, or at least also in your password manager. Otherwise a single compromised repo could replace both the list and its checksum.

If the controller docs are really your general ops runbook, not Ansible-specific, a top-level `security/` section in them would work too. Just make sure the Diceware procedure can be checked out and printed without the controller running.

Figer print confirmation on console

```bash
ssh -i ~/.ssh/example-org-raw-initial-id_ed25519 -o IdentitiesOnly=yes initial@203.0.113.10
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
256 SHA256:EXAMPLEexampleEXAMPLEexampleEXAMPLEexample0 root@deb13-vt (ED25519)
```

## SOlutions

On a GNOME or Cinnamon desktop, which is what Mint runs, `gnome-keyring-daemon` can provide its own SSH agent and export `SSH_AUTH_SOCK` pointing at its socket, so when you run `ssh-add` the key often lands in gnome-keyring rather than the plain OpenSSH `ssh-agent`. gnome-keyring then stores the passphrase in your login keyring and can auto-unlock it at login, which is convenient, but its agent historically lagged OpenSSH on newer key types and options, so ed25519 keys and constraints like `ssh-add -t` or `-c` are where you see oddities, including the "agent refused operation" signing failures. The two agents also compete: whichever one owns `SSH_AUTH_SOCK` is the one ssh talks to, so a key loaded into one is invisible to the other, which is a common reason a key "isn't loaded" even though you just added it. If you want predictable behaviour for automation, the usual fix is to disable gnome-keyring's SSH component (its `gnome-keyring-ssh` autostart) and let the real `ssh-agent` own the socket, then confirm with `echo $SSH_AUTH_SOCK` and `ssh-add -l` that you are talking to the agent you think you are.

## A few concrete fixes, most reliable first.

Make the OpenSSH agent own the socket, disable gnome-keyring’s SSH component. Mask the autostart so it stops grabbing `SSH_AUTH_SOCK`:

```sh
cp /etc/xdg/autostart/gnome-keyring-ssh.desktop ~/.config/autostart/ 2>/dev/null
printf 'Hidden=true\nX-GNOME-Autostart-enabled=false\n' >> ~/.config/autostart/gnome-keyring-ssh.desktop
```

Log out and back in, then run a real agent and point your shell at it. The simplest durable setup on a systemd distro is the user service:

```sh
systemctl --user enable --now ssh-agent.service 2>/dev/null
echo 'export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"' >> ~/.profile
```

If there is no `ssh-agent.service`, start one per login instead with `eval "$(ssh-agent -s)"` in your shell profile.

Let ssh manage key loading so you stop doing it by hand. In `~/.ssh/config`:

```
AddKeysToAgent yes
IdentitiesOnly yes

Host ex2-test 10.0.0.*
    User initial
    IdentityFile ~/.ssh/example-org-raw-initial-id_ed25519
```

With `AddKeysToAgent yes`, the first connect prompts for the passphrase once and loads the key for the session, and `IdentitiesOnly yes` stops the key spraying that tripped `MaxAuthTries` earlier.

Check which agent you are actually talking to before debugging anything else:

```sh
echo "$SSH_AUTH_SOCK"     # a keyring path means gnome-keyring still owns it
ssh-add -l                # is the right key there?
```

A quick per-shell override if you just need a clean agent now, without logout:

```sh
eval "$(ssh-agent -s)"
ssh-add -t 8h ~/.ssh/example-org-raw-initial-id_ed25519
```

One caveat worth checking: recent gnome-keyring versions dropped the SSH agent entirely, so on an up-to-date Mint the keyring may not be in the picture at all. If `echo $SSH_AUTH_SOCK` already shows an `ssh-agent` or `XDG_RUNTIME_DIR` path rather than a `keyring` one, OpenSSH’s agent is already in charge and the autostart step is unnecessary.