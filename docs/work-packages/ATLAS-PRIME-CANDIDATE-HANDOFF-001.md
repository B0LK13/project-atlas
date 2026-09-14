# ATLAS-PRIME-CANDIDATE-HANDOFF-001 — eindoverdracht CLOSE-IMPLEMENTATION-GAPS

Datum: 2026-09-14. Deze overdracht rondt uitsluitend het werkpakket
ATLAS-PRIME-LOCAL-001-CLOSE-IMPLEMENTATION-GAPS af en verbindt haar met de
bestaande pilot/diagnoselijn. Zij is geen nieuwe implementatiemissie, geen
provider- of deploymentautorisatie, geen tijdverlenging en geen automatische
releasevrijgave.

## 1. Kandidaatidentiteit (bewijsbinding)

| Binding | Waarde | Bewijs |
| --- | --- | --- |
| Kandidaat-HEAD (freeze) | `913bc791637acc9afecb8a2429f5ba4e8f2dc709` | matrix pin registry; IV-review |
| Kandidaat-tree | `f34a1684fc005ca2aed5ebecd03d29bc98cfe3d4` | idem, `git rev-parse` geverifieerd |
| Branch / remote / ref | `feat/prime-local-001` @ `https://github.com/B0LK13/project-atlas.git`, ref `refs/heads/feat/prime-local-001` **afwezig** (ongepubliceerd) | `git ls-remote`; remote `refs/heads/main` = `b87b4a226f` is een andere ref, niet de kandidaatbranch |
| Docs-record bovenop freeze | `cc25b838` (matrix-freeze), `04c9cf27` (IV-verdict) — docs-only | `git diff --stat` per commit |
| Upstream runtime-pin | `5d25a44bd22e1c1fe8321e141cd6c3932563d14c` (package 0.9.4) | runtime-manifest `upstream_sha` + `source_commit_verified: true`; install-script `SOURCE_SHA` |
| Hostpatch | id `prime-agent-5d25a44-atlas-child-admission-v1`, sha256 `226405200865db6f677e846da420d2fa7c04e8b42d5bef8b77c1ffffb7416dba` | `patches/…` (werkend én gecommit), constante in `prime_agent.py`, runtime-manifest; drieweg-gelijk door de verifier |
| Runtime/config-identiteit | devcheckout `/home/gebruiker/prime-local-001-runtime` @ upstream-pin + ongecommitte gepinde hook; manifest `adapter_version: prime-agent-atlas-adapter-v1`, lockfile `409e3547…` | `atlas-prime-runtime-manifest.json`; runtime-008 is schoon (geen hotpatch) |
| Test-head | clean worktree `/home/gebruiker/atlas-prime-verify-001` @ `913bc791` (status clean) | `git rev-parse` bij verificatie |
| Niet-auteur-verdict | **PASS, 0 blockers**, eigen overgedraaide battery (266 tests, ruff, mypy 458, TS 5/5, probe 4/4) | `docs/orchestration/program/evidence/PRIME-LOCAL-001-IV-REVIEW.md` |
| Supervisoracceptatie | exact verdict PASS aanvaard in programma-evidence, expliciet zonder nieuwe bevoegdheden | zelfde IV-doc, slotsectie |

Chronologie wordt niet uit korte hashes afgeleid: volgorde en tijdstippen
staan in de git-geschiedenis. Het reviewbereik `3f3ee03b^..cc25b838` dekt de
freeze exact: het loopt 21:11:59 → 22:25:13 en bevat de gefroze HEAD
`913bc791` (22:18:22), de laatste hostpatch (geregenereerd vóór `bba5204e`
21:44:22, gecommit daarin) en de docs-commits; het verdict-doc `04c9cf27`
(22:36:50) is de acceptatierecord erbovenop.

Bekende buiten-freeze toestand (niet herschreven): de pilot-lane heeft
ongecommitte WIP in dezelfde worktree (`prime_inference_proxy.py`,
`prime-local-001-inference-relay.py`, bijbehorende test, en een
`adapter_version: v2`-bump in de docs-copy van de runtime-manifest). Dat is
onderdeel van de pilotlijn, geen deel van deze freeze; elke latere commit
heropent impactanalyse (matrix pin registry).

## 2. Geaccepteerde scope van dit werkpakket

CLOSE-IMPLEMENTATION-GAPS is voldaan en via de bestaande acceptatieroute
(matrix + niet-auteur-IV + supervisoracceptatie) gesloten: matrixcorrectie
met pinregistratie; voltooide native admission (hostpatch reserve/commit/
release voor child-uitvoering; model/depth-allowlist, fencing, dedup,
parent-binding, budget; fail closed); alle vereiste modelvrije hostroutetests;
P5/isolatie-bindingen (sandbox-probe 4/4, validatorpins incl. `--bind=`-evasie,
trusted policy, knowledge-capture als lokale evidence, rollback- en
Studio-reconnect-bewijzen); P7-autorisatiegap zonder grant te verzinnen.
De kandidaat is de kandidaat van dit werkpakket — niet automatisch de basis
van andere missies.

## 3. Herbruikbaar bewijs (alleen toepasselijk)

- Deze lijn: 266 tests op de clean tree @ `913bc791`, ruff/mypy clean, 14/14
  netwerk-geïsoleerde smoke, 4/4 sandbox-probe, 5/5 TS-admission — alles
  door de niet-auteur zelf overgedraaid.
- Prior-programma (alleen op eigen pins): IV PASS op `b3273231`
  (`…/atlas-r-deploy/prime-local-001/evidence/P6-INDEPENDENT-REVIEW.md`),
  P0–P6 op runtime-008 @ `95594566`. Dekt `6ded02a6` en deze lijn niet.
- Lijnverwantschap (gecontroleerd, geen aanname): `af3e4691` is voorouder van
  `913bc791` (zelfde branch, provider-classificatie/-matrixcommits 20:39–20:52);
  de Qwen3-pilot deelt dezelfde bron- en runtimegeschiedenis (zelfde upstream
  `5d25a44bd`, zelfde hostpatch, zelfde devcheckouts) plus eigen ongecommitte
  proxy-WIP. Geen cherry-pick, geen overschrijving, geen heractivering van een
  oudere kandidaat.

## 4. Werkelijk open taken — ontbrekende voorwaarde en hervattrigger

| Open taak | Ontbrekende voorwaarde | Hervattrigger |
| --- | --- | --- |
| Prime real-model toolcall / codingslice (pilotlijn) | voldoende model-tool-use (de Qwen3 1.7B-pogingen `kernel-bound-rpc-1..-6` en `kernel-bound-capability-1/-2` leverden **geen echte ipython-toolcall**: poging -6 deed één echte inferentie met `agent_end` maar alleen reasoning-text; capability-1/-2 onzeker/geen call) + reviewed proxy/IPC-brug | nieuw ownerbesluit; de geldige pilotgrant zegt expliciet dat geen verdere kleinere-modelpogingen geautoriseerd zijn |
| ATLAS-PRIME-REALIGN-001 / AS-PRIME-TOOLCALL-DIAGNOSTICS-001 | taak is **niet geconstitueerd**: nergens in het dossier een ownerbesluit, enrollment of executorgrant; alleen voorstel-/verkenningstekst (inventory + proxy-WIP) — daar wordt geen taak of bevoegdheid van gemaakt | ownerbesluit via bestaande queue/handoff-route; pas daarna kan de supervisor haar onder geldige admission/ownership/executorgrant vervolgen |
| CI op de kandidaat | billingherstel GitHub-account; run op de gefroze head `913bc791` — een rerun van de oude run dekt de nieuwe head niet | billingherstel, daarna exact-head CI |
| Canonieke kennisontvangst | Knowledge Plane receipt-pipeline aansluiting (lokale capture bestaat; canoniek blijft OPEN) | apart werkpakketbesluit |
| Deployment / canary-rollback gate | deploymentautorisatie (niet verstrekt). De rollback-rij in de matrix blijft beperkt tot adapter-scope: cancel-na-CERTIFIED met intacte evidence is **geen** runtime-/deploymentrollback-bewijs | ownerdeploymentbesluit (canary-formaat) |
| Menselijke IV | afzonderlijke, expliciet vereiste menselijke gate — de agent-IV (PASS) vervangt die niet | menselijke reviewer wordt aangesteld |

Resultaten van een andere executor tellen niet als Prime-real-modelbewijs.

## 5. Grantledger (status per grant)

| Grant | Status |
| --- | --- |
| Prime cloud/paid real-model | **nooit verstrekt** (P7-gapdoc) |
| Kimi-probe 0/1 (auth 007) | **geldig, onaangeroerd** — niet door Prime gebruikt |
| Lokale Qwen3-pilot (ownerbesluit) | **beperkt geldig**: alleen lokaal `qwen3:4b`-achtig traject, geen cloudfallback; kleinere-modelpogingen **uitgeput/onvoldoende** (geen toolcall); artifact `qwen3:4b` aanwezig (digest `359d77…74fae7`), tool-use-route onbewezen |
| REALIGN/TOOLCALL-diagnosetaak | **niet geconstitueerd** (zie §4) |

Een vroeger verleende grant is geen huidige onbeperkte bevoegdheid: geen
vierde capabilitycyclus, geen modelwissel, geen budgetreset.

## 6. Toepasselijke owneracties (niet blind overgenomen)

1. Billingherstel → exact-head CI op `913bc791`.
2. Besluit volgende pilotstap (tool-use-route of alternatief), alleen binnen de
   bestaande pilotgrant of met een nieuw besluit.
3. Ownerbesluit indien REALIGN/TOOLCALL-DIAGNOSTICS als taak moet bestaan.
4. Menselijke IV aanstellen (losse gate).
5. Publicatiebesluit (ref `refs/heads/feat/prime-local-001` aanmaken) indien
   gewencht — Q08-logica, niet automatisch.

Bewaking loopt uitsluitend via bestaande geautoriseerde mechanismen
(`program status/events/control`, matrix, evidence-dossier) binnen deadline
en budget; er is geen model-wachtlus of routinebevestiging opgenomen.
