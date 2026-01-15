# Karton File Detection
> [Karton](https://github.com/CERT-Polska/karton) service to run [Detect It Easy](https://github.com/horsicq/Detect-It-Easy), [TrID](https://mark0.net/soft-trid-e.html), and [Magika](https://github.com/google/magika) on samples.

## Prerequisites

This is to be used as part of a [Karton](https://github.com/CERT-Polska/karton) pipeline. It has been setup as a [Docker](https://www.docker.com/) container.

Recommended **docker compose** setup:

```yml
karton-file-detection:
  build:
    context: karton/file_detection
  tty: true
  develop:
    watch:
      - action: sync+restart
        path: karton/file_detection
        target: /app
        ignore:
          - karton/file_detection/.venv/
      - action: rebuild
        path: karton/file_detection/uv.lock
      - action: rebuild
        path: karton/file_detection/Dockerfile
  depends_on:
    - karton-system
    - mwdb-web
  volumes:
    - ./karton.docker.ini:/etc/karton/karton.ini
```

## Behavior

For a given sample, run **DiE**, **TrID**, and **Magika** on it and:
1. Add the `packer_type` and `packer_name` found by **DIE** as **tags**
2. Extract specific fields from the responses and add them to the sample as **attributes**


**Consumes:**
```json
{"type": "sample", "stage": "recognized"}
```

**Produces:**
```json
{
  "headers": {"type": "sample", "stage": "analyzed"},
  "payload": {
    "sample": sample,
    "tags": <DiE tags>,
    "attributes": {
      "die": <Minimized DiE result>,
      "trid": <Minimized TrID result>,
      "magika": <Parsed Magika result>,
    }
  }
}
```

## Attributes

### Detect it Easy

**Key.** `die`

**Label.** DiE

**Description.** Parsed output of running Detect it Easy on the sample

```jinja
<!-- Rich Template -->

{{#value}}
**{{filetype}}**:
{{#values}}
- {{string}}
{{/values}}
{{/value}}
```

### TrID

**Key.** `trid`

**Label.** TrID

**Description.** TrID is a utility designed to identify file types from their binary signatures. It may give several detections, ordered by higher to lower probability of file format identification (given as percentage).

```jinja
<!-- Rich Template -->

{{#value}}
**{{extension}}**: {{name}} -> {{percentage}}% 
{{/value}}
```

### Magika

**Key.** `magika`

**Label.** Magika

**Descriptions.** Fast and accurate AI powered file content types detection.

```jinja
<!-- Rich Template -->

{{#value}}
**{{label}}**{{#description}}({{.}}){{/description}}:
- **Extensions:** {{extensions}}
- **Group:** {{group}}
- **Score:** {{score}}
{{/value}}
```



