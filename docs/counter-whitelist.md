# Chapter 2: Allowed referrer and IP checking

**Check whitelist (recommended)** controls whether incoming requests must match the **Allowed Domain List**. This list contains allowed website domains and IP addresses.

A referrer identifies the website a request came from, when that information is supplied. The IP address identifies the source of the request and may belong to a server sending it on behalf of the petition website. A request can pass the whitelist by matching either an allowed domain or an allowed IP address. The existing valid API-key override also remains available.

Whitelist checking is **on by default** for existing and new counters, including counters created through an API key. Disabling it affects only the selected counter.

## Why you might disable the check

Some petition platforms do not provide the expected referring website, or send requests through another domain or server. Legitimate requests can then fail with **“Not in allowed list”** and HTTP **400**.

Configuring the correct allowed domain or IP address is the preferred approach. If that is impractical, the person setting up the counter can disable whitelist checking. This option can help when the integration developer cannot easily inspect request headers or control which source information the platform sends.

## How to change the setting

1. Open **Create counter** or **Edit counter**.
2. Find **Check whitelist (recommended)**.
3. Leave it on to check the allowed domain/IP list, or turn it off to skip that check for this counter.
4. Save the counter.

You can turn the check back on through Edit counter at any time. Before doing so, confirm that legitimate requests match an allowed domain or IP address, or use the existing valid API-key override. Re-enabling the check does not remove unwanted counts already recorded.

## Risks of disabling it

With whitelist checking off, requests from other websites, unknown IP addresses, or without a referrer can reach the counter, subject to its remaining checks.

Someone who copies the counter URL could use it elsewhere and generate unwanted traffic or inflate the total. Reports may then include activity that did not come from your petition. The person configuring the counter must decide whether this risk is acceptable.

## Checks that remain active

Disabling this setting skips only the allowed domain/IP check. It does not disable:

- Disallowed URL-pattern checks.
- Request rate limits.
- Counter existence checks and donation amount limits.
- Email-hash validation in the counter's selected mode.
- Email-hash duplicate detection when a hash is supplied.
- Authentication and permissions for creating or editing counters.

Blocked URL patterns still depend on the referring path being supplied. They cannot identify a path that is absent from the request. Disabling the whitelist will not resolve an email-hash format error returning 422.

## Understanding counting response codes

| Code | Meaning for the counting endpoint |
|---|---|
| **200** | Request handled: either the counter increased or an already-counted fingerprint was skipped. Read the response message to distinguish them. |
| **400** | The source failed the whitelist, a referring URL pattern was blocked, or the counter name was missing. |
| **404** | The requested counter was not found. |
| **422** | The email-hash format was rejected or the donation amount was outside the permitted range. |
| **429** | Too many requests; the rate limit was reached. |
| **500** | An unexpected processing or database error occurred. |

## API configuration

To disable whitelist checking when creating a counter through the API:

```json
{"name": "petition_example", "whitelist_check_enabled": false}
```

Omit the setting or send `true` to keep checking enabled on creation. Use the usual API-key authentication for `/api/createcounter`.

The other creation routes and authenticated JSON update route support the setting too. Omitting it from a JSON update preserves the current setting. A counting request cannot disable the check through a query parameter.

Existing counters without the saved setting continue to check the whitelist. No database migration is required for this default to apply.

[Previous: Email hash validation](email-hash-compatibility.md)
