# Chapter 1: Email hash validation — Strict and Legacy compatibility

The counter supports older integrations while applying stricter email-hash validation to new counters by default. Existing counters use **Legacy compatibility** unless explicitly changed. New counters use **Strict** by default, including counters created through an API key. An authorised user can select either mode when creating or editing a counter.

## What is an email hash?

An `email_hash` is a fingerprint generated from an email address. The integration sends this fingerprint to help the counter recognise an email that has already been counted for that counter.

Hashing creates the fingerprint. Encoding determines how the fingerprint is written as text. A rejected format does not necessarily mean the hashing itself is wrong.

## How the two modes work

| Mode | Accepted format | Intended use |
|---|---|---|
| **Strict** | 16–128 letters, numbers, underscores (`_`), or hyphens (`-`). No spaces, `+`, `/`, or `=` padding. | New integrations and older integrations that have been updated and tested. |
| **Legacy compatibility** | The strict format plus the older Base64 characters `+` and `/`, with up to two trailing `=` characters. It also handles `+` converted to a space during URL processing. The fingerprint must still contain 16–128 characters before padding. | Existing integrations that send the older format. |

Compatibility mode still validates the input. It does not accept arbitrary text. Existing counters without a saved mode automatically use compatibility mode; this does not depend on their creation date.

Both modes recognise equivalent old and new representations when checking historical duplicates. Changing the representation therefore does not by itself count the same fingerprint again. Previously recorded totals are not corrected, and previously rejected requests are not automatically replayed.

## Why a request returns 422

HTTP **422** means a supplied value does not meet the counter's validation rules. For example, Strict mode rejects this older-format hash because it contains `+` and ends with `=`:

```text
zn+946yDl9gbgfnXoMO6gCKSCGKPJtsME5NN2KXhIaU=
```

Its supported URL-safe equivalent is:

```text
zn-946yDl9gbgfnXoMO6gCKSCGKPJtsME5NN2KXhIaU
```

For an integration using Base64, its developer should keep the existing hashing method, replace `+` with `-`, replace `/` with `_`, remove trailing `=`, and build the URL using a query-string encoding function. Apply the conversion consistently to every request. Simply URL-encoding the original value does not satisfy strict validation.

A request rejected with 422 does not increase the counter. An out-of-range donation amount can also cause 422, so check the response message to identify the reason.

## Switching an existing counter to Strict

1. Ask the integration developer to confirm that it sends the supported strict format consistently.
2. Test the integration against a test counter set to **Strict**. Confirm that a new fingerprint counts once and a repeat is recognised as a duplicate.
3. Open **Edit counter** for the production counter.
4. Set **Email hash validation** to **Strict**, then save.
5. Monitor requests for 422 responses. If format problems appear, return the counter to **Legacy compatibility** while the integration is corrected.

Verification is manual. The application does not automatically verify an integration or switch its mode.

## What remains unchanged

Whitelist checking, blocked URL patterns, rate limits, counter existence checks, donation limits, and duplicate handling remain active as before. Strict mode does not make `email_hash` mandatory: requests without it retain their existing behaviour and cannot use email-hash duplicate detection.

## API configuration

Creation and authenticated JSON updates accept:

```json
{"email_hash_mode": "strict"}
```

Use `"legacy"` for compatibility mode. Omitting the field during creation defaults to Strict. Omitting it from an update preserves the current mode. A counting request cannot override the saved mode.

[Next: Allowed referrer and IP checking](counter-whitelist.md)
