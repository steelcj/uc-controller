---
title: "Contracts and policies"
date: 2026-11-18
author: "Christopher Steel"
status: "Index"
description: "The contracts uc-controller consumes and produces, and the policies it implements, from uc-contracts, with the versions it supports."
---

# Contracts and policies

## Abstract

uc-controller does not copy contracts or policies. It lists the ones it consumes, produces or implements here, as the uc-contracts README describes <a name="apa-steel-uc-contracts-citation"></a>([Steel, 2026d](#apa-steel-uc-contracts-reference)). The documents themselves live in uc-contracts.

## Contracts and policies

| Document | Version | Role | Where in uc-controller |
| --- | --- | --- | --- |
| <a name="apa-steel-raw-node-contract-citation"></a>`raw-node` ([Steel, 2026c](#apa-steel-raw-node-contract-reference)) | 0.3.0, 0.3.1 | Ingress | `ingress/playbooks/05_admit.yml` admits nodes that meet it. `scripts/check_raw_confirmation.py` checks their confirmations and accepts both versions, since 0.3.1 changed wording only |
| <a name="apa-steel-onboarding-egress-citation"></a>`onboarding-egress` ([Steel, 2026a](#apa-steel-onboarding-egress-reference)) | 0.3.0 | Egress | `ingress/playbooks/10_onboard.yml` produces onboarded nodes. Clauses marked "Not yet" in the contract are not delivered, and admitted contract nodes are not onboarded yet |
| <a name="apa-steel-privileged-access-citation"></a>`privileged-access` ([Steel, 2026b](#apa-steel-privileged-access-reference)) | 0.1.0 | Implements, partly | From the raw node admission kickoff on: batch passwords are generated and kept in batch files outside every repository, read only through the `uc_secret` lookup (PA-PWD-01, partly PA-PWD-02; see `en/docs/guides/batch-secrets.md`), and admitted nodes are reached with strict host key checking against keys recorded at admission (PA-HOST-01, PA-HOST-02) |

How each clause is met is recorded in the final report of the kickoff that delivered it, under `en/docs/sessions/`.

`en/docs/contracts/uc-raw-node-contract.md` is an older pointer to the raw node contract, at a path in uc-contracts that has since moved. The links on this page are current.

## References

<a name="apa-steel-onboarding-egress-reference"></a>Steel, C. (2026a). *Onboarding egress contract* (Version 0.3.0) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-onboarding-pipeline/2-ansible-ingress-egress-contract/uc-onboarding-egress-contract.md
[Return to citation](#apa-steel-onboarding-egress-citation)

<a name="apa-steel-privileged-access-reference"></a>Steel, C. (2026b). *Privileged access policy* (Version 0.1.0) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-policies/privileged-access/uc-privileged-access-policy.md
[Return to citation](#apa-steel-privileged-access-citation)

<a name="apa-steel-raw-node-contract-reference"></a>Steel, C. (2026c). *Raw node contract* (Version 0.3.1) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md
[Return to citation](#apa-steel-raw-node-contract-citation)

<a name="apa-steel-uc-contracts-reference"></a>Steel, C. (2026d). *uc-contracts* [Repository README]. GitHub. https://github.com/steelcj/uc-contracts
[Return to citation](#apa-steel-uc-contracts-citation)

## Changelog

| Date | Notes |
| --- | --- |
| 2026-11-18 | First version, from the raw node admission kickoff |
