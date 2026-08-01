# Vault Path Mapping

## Raw events

```text
sources/agent-events/YYYY/MM/DD/<event-id>.md
```

## Normalized events

```text
projects/<project-slug>/events/YYYY/MM/<event-id>.md
```

## Project log and work package

```text
projects/<project-slug>/log.md
projects/<project-slug>/work-packages/<work-package-slug>.md
```

## Conditional concepts

```text
projects/<project-slug>/decisions/<decision-id>.md
projects/<project-slug>/validations/<validation-id>.md
projects/<project-slug>/risks/<risk-id>.md
projects/<project-slug>/issues/<issue-id>.md
projects/<project-slug>/deployments/<deployment-id>.md
projects/<project-slug>/components/<component-id>.md
```

## Spool

```text
<repository>/.atlas-spool/<event-id>.md
```

## Path rules

- lowercase kebab-case generated filenames;
- POSIX-style relative metadata paths;
- no user home paths in canonical metadata;
- no traversal;
- writes remain inside resolved roots;
- stable filenames across retries.
