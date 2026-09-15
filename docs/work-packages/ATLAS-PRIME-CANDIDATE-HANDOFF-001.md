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
| ATLAS-PRIME-REALIGN-001 / AS-PRIME-TOOLCALL-DIAGNOSTICS-001 | **gesloten 2026-09-15** (zie §7.3–§7.5 en §8): ownerbesluiten bijlage, executor gekoppeld, dispatch run.1.519a148f `acceptance_passed: true`, taak CERTIFIED, niet-auteur-IV PASS; acceptatie-equivalentie en scope-afwijking vastgelegd in §8.2/§8.4 | geen hervattrigger voor deze taak; alleen de ownerdisposition voor de §8.4-afwijking (behoud / targeted revert / afsplitsing) |
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
| REALIGN/TOOLCALL-diagnosetaak | **geconstitueerd 2026-09-15** (ownerbesluiten als bijlage; executor `codex-diagnostics-001` ACTIVE op canonieke registry; dispatch successor-2 loopt — §7.4) |

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

## 7. Addendum 2026-09-15 — bewijsverduidelijking (A) en bootstrapstatus (B)

Dit addendum verduidelijkt twee bewijs-/statuspunten en legt de uitvoering van
ATLAS-EXECUTOR-BOOTSTRAP-001 vast. Het herschrijft geen earliere verdicts: de
IV PASS op de freeze en de matrix blijven ongewijzigd op hun pins.

### 7.1 Lijnverwantschap en reviewbereik — commitgraphbewijs

Verificatie in `/home/gebruiker/atlas-prime-local-001` (branch
`feat/prime-local-001`), exacte commando's en uitkomsten:

| Commando | Uitkomst |
| --- | --- |
| `git merge-base --is-ancestor af3e4691 913bc791` | exit 0 — `af3e4691` is voorouder van `913bc791` |
| `git rev-list --count af3e4691..913bc791` | 7 |
| `git rev-list --count --ancestry-path af3e4691..913bc791` | 7 — pure lijn, geen zijtakken/merges |
| `git merge-base --is-ancestor 3f3ee03b cc25b838` | exit 0 — reviewbereik goed gevormd |
| `git merge-base --is-ancestor 913bc791 cc25b838` | exit 0 — freeze ligt ín het reviewbereik |
| `git merge-base --is-ancestor 04c9cf27 cc25b838` | exit 1 — verdict-doc is kind van het reviewplafond (by construction) |

Conclusie: het reviewbereik `3f3ee03b^..cc25b838` dekt de freeze `913bc791`
én de laatste hostpatch; het verdict-doc `04c9cf27` zit er direct bovenop.
Chronologie volgt uit git-geschiedenis (tijdstempels/volle hashes), nooit uit
volgorde van korte hashes. Dit bevestigt §1 en §3; er was geen ongedekte
delta, dus geen testherhaling.

### 7.2 Verdictbindingscontrole (bron/patch/runtime)

Op de gecommitte blobs bij `913bc791`:

- `git show 913bc791:patches/prime-agent-5d25a44-atlas-child-admission-v1.patch | sha256sum`
  = `226405200865db6f677e846da420d2fa7c04e8b42d5bef8b77c1ffffb7416dba` =
  patchconstante in `prime_agent.py` = `patch_sha256` in
  `prime-local-001-runtime-manifest.json` (drieweg-gelijk).
- Manifest bij die commit: `adapter_version: prime-agent-atlas-adapter-v1`,
  `upstream_sha 5d25a44bd22e1c1fe8321e141cd6c3932563d14c`,
  `source_commit_verified: true`.

### 7.3 "Lege enrollmentregistry"-observaties naast elkaar

De eerdere constatering "diagnosetaak niet geconstitueerd / lege registry" was
een **dossierstand op een tijdstip**, geen globale uitspraak. Drie observaties:

| Wie / wanneer (UTC) | Host | Checkout / dossierstand | Gebruikte registry/state-root | Bevinding |
| --- | --- | --- | --- | --- |
| Codex-agent `01a0a06c`, 2026-09-14 20:40:17Z (herhaald 20:40:44Z, 20:41:02Z) | Probook-450 | dossier @ `04c9cf27` (tree `04cd857b`) | `/home/gebruiker/atlas-agents` (bestond niet) + enkele gecontroleerde paden | `agents: []`; taak als geblokkeerd gerapporteerd, geen self-enrollment |
| Zelfde agent, 20:56:23Z | zelfde | zelfde | canoniek afgeleid uit DEPLOYMENT-MANIFEST-015: `…/supervisor-autonomous-009/registry` | alleen `q-agent-009` (historisch); bootstrap vervolgens zelf uitgevoerd: enroll 20:58:40Z, assign 21:00:12Z, dispatch (run 1 model-fout; successor worker compleet maar acceptance=false) |
| Deze sessie, 2026-09-15 ±06:31Z | zelfde | `atlas-prime-local-001` @ `03bc4459` | canoniek registry + queue | `codex-diagnostics-001` ACTIVE, assigned; queue-binding conform manifest; diagnostische lijn bestaat dus wél |

De ownerbesluiten bestaan inmiddels als bijlage: **ATLAS-PRIME-REALIGN-001**
(taaktoelating AS-PRIME-TOOLCALL-DIAGNOSTICS-001) en
**ATLAS-EXECUTOR-BOOTSTRAP-001** (begrensde operatorbootstrap). Deze vervallen
de eerdere "niet geconstitueerd"-status; zie bijgewerkte rijen in §4/§5.

### 7.4 Bootstrapstatus ATLAS-EXECUTOR-BOOTSTRAP-001

Contextvaststelling (één keer, geen secrets gelogd): host `Probook-450`,
OS-user `gebruiker`, cwd van deze operator-sessie
`/home/gebruiker/Projects/project-atlas`; operator-CLI
`/home/gebruiker/atlas-prime-local-001/.venv/bin/python -m project_atlas.orchestration.program.cli`;
canonieke registry/state/queue afgeleid uit
`…/atlas-supervisor-deployment-015/DEPLOYMENT-MANIFEST-015.json`
(registry root `…/supervisor-autonomous-009/registry`); bron van `agents[]` =
`registry/.atlas/orchestration/program/agents.json` (leesbaar, geen fallback,
geen leesfout).

- **Binding hergebruikt**: bestaande ACTIVE enrollment `codex-diagnostics-001`
  (enrolled 2026-09-14T20:58:40Z) — geen nieuwe enrollment nodig.
- **Programbinding via ondersteunde route**: `agent assign` op de canonieke
  registry naar `program-successor-2.json` op 2026-09-15T06:38:10Z
  (program_sha256 `2383b3e12a13fad8cbdb0679130306fda99c6fd98b608be4fdb688acfbfe0963`,
  vooraf `program validate` → `valid: true`); readback bevestigd.
- **Acceptance-defect forensisch vastgesteld**: de recorded acceptance-fout van
  de successor-run (21:11Z) was een program-declaratiedefect, geen workerdefect.
  De programmafiles zijn ná de run bewerkt (mtime 23:14:36 +0200); runtime-008
  heeft een **niet-editable** `project_atlas 2.0.0` zonder `pytest-cov`, dus de
  gedeclareerde commando kan daar nooit slagen (lokaal aangetoond:
  cov-args-usagefout resp. `ModuleNotFoundError` op de nieuwe module). De
  gecorrigeerde acceptance-route (workspace-`src` op `sys.path`, addopts
  gewist) is lokaal groen: **73 passed in 8,98s**. Successor-2 draagt die
  gecorrigeerde argv; geen wijziging in securitypolicy of acceptatiecriteria.
- **Dispatch**: `program service start` op 2026-09-15T06:38:24Z, verse
  state-root `state-successor-2`, service-pid 501639, `--max-rounds 1`.
  Resultaat: **PENDING — zie §7.5**.
- **Grenzen**: zelfde limieten (1 worker, 1 launch, 5400 s, geen recursie,
  geen model-pin, geen providergrant, geen nieuwe inference); verbruik van
  deze aanvulling wordt apart geregistreerd uit de run-evidence. Deze
  executorbewijs telt niet als Prime-real-modeltoolcall of native delegatie.

### 7.5 Successor-2 resultaat

Dispatch bewijsbaar en het taakresultaat is echt:

- Supervisor-dispatch: poging
  `atlas-prime-toolcall-diagnostics-001-successor-2.AS-PRIME-TOOLCALL-DIAGNOSTICS-001.run.1.519a148f`,
  gestart 2026-09-15T06:38:24Z, beëindigd 06:39:44Z, exit 0, confidence
  CONFIRMED, supervisor-pid 501639.
- **Supervisoracceptatie: `acceptance_passed: true`** —
  `diagnostic-tests`: 73 passed in 8,64s (gesuperviseerde omgeving, geen
  codex-sandbox); `git_tree_changed`: 9 gewijzigde paden. Taakstatus
  **CERTIFIED** ("every acceptance condition observed to hold"). De worker
  rapporteerde eerlijk 69/4 onder zijn eigen sandbox en voerde géén wijzigingen
  door ("no changes made; existing implementation preserved").
- **Aanvullend verbruik (apart geregistreerd, zoals vereist)**: 488.204
  input-tokens (waarvan 418.816 gecached), 1.229 output-tokens, 40
  reasoning-tokens; geen kostenpost verzonnen (adapter rapporteert alleen
  tokens). Geen providergrant, geen modelwissel, geen budgetreset.
- **Niet-auteur-IV van de worker-delta** (uitgevoerd door deze sessie; de
  worker-auteur is `codex-diagnostics-001`): **PASS, 0 blockers**, twee
  observaties:
  1. `docs/.../prime-local-001-runtime-manifest.json` (adapter_version
     v1→v2) valt buiten de gedeclareerde mutation_paths; docs-evidentie,
     consistent met de `ADAPTER_VERSION`-bump in `prime_agent.py`. De
     freeze-bindingen blijven intact: `CHILD_ADMISSION_PATCH_SHA256 =
     226405200865…` en `PRIME_UPSTREAM_SHA = 5d25a44bd…` ongewijzigd; de
     toelatingspoort hangt aan de patch-hash, niet aan het versielabel.
  2. `scripts/prime-local-001-inference-relay.py` is ongetrackt en
     byte-identiek aan de bestaande parallelle pilot-WIP — niet door deze
     worker geautord, geen deel van de delta, ongemoeid gelaten.
  Verder: zeven diagnostische statussen correct en alleen-lezen over
  opgeslagen evidence; evidentiecorrecties (rpc-6 `no_structured_toolcall`,
  capability-1 `kernel_start_failure` met geldige gestructureerde call,
  capability-2 `unknown`) met SHA-256's vastgelegd; `control.py`-projectie
  alleen-lezen, fail-closed, pad-veilig (symlink-escape-test), additieve
  contract-bump volgens conventie; geen inference, geen policywijziging.
- **Bewijsgrenzen**: dit alles sluit de diagnosetaak en haar
  observability-eis; het is **geen** Prime-real-modeltoolcall-bewijs en geen
  native Prime-delegatie. De open punten uit §4 (real-model slice, CI,
  canonieke kennisontvangst, deployment, menselijke IV) blijven onveranderd
  open. Dit addendum is tevens het publicatie- en coördinatieregister voor de
  betrokken agents (zie §8).

## 8. Addendum 2026-09-15 (2) — verwerking run.1.519a148f per eigenaaraanvulling

Uitgevoerd als bevoegde-operatorcontrole op uitsluitend bestaand bewijs: geen
nieuwe modelcalls, geen coding-/IV-launches, geen budgetverlenging, geen
publicatie/merge/uitrol, geen gateversoepeling.

### 8.1 Publicatie en afstemming parallelle opdrachten

- **Gepubliceerd via deze overdracht**: resultaat run.1.519a148f (attempt
  `…successor-2.…run.1.519a148f`, TERMINAL/exit 0, `acceptance_passed: true`,
  taak CERTIFIED) met canonieke locatie
  `…/prime-local-001/diagnostics-001/state-successor-2/.atlas/orchestration/program/`
  (state.json, leases.json, events.jsonl) en evidence-hashes: acceptance.json
  `cb71b940…`, codex-events.jsonl `4687bd10…`, codex-last.txt `17e09865…`,
  codex-summary.json `41cbb057…`.
- **ATLAS-VERIFICATION-ROUTE-IMPLEMENT-001**: bestaat nergens als canoniek
  record — queue (`approved-work-queue.json`) en registry nagekeken, geen
  entry; zij leeft als ownerbijlage aan de andere lane en als bouw-WIP in de
  worktree (`src/project_atlas/orchestration/program/verification.py`,
  `tests/unit/test_orchestration_program_verification.py` en src-wijzigingen in
  `acceptance.py`, `cli.py`, `models.py`, `supervisor.py` — op moment van
  schrijven ongecommitte van die lane). Tijdens deze checks: **HOLD** — geen
  nieuwe launches onder die opdracht. Geen enkel proces beëindigd; alle
  routecode en -evidence ongemoeid bewaard; geen reset/staging/verwijdering.
- **Niet gelijkgeschakeld**: run.1.519a148f is een nieuwe coding-dispatch, geen
  read-only herbeoordeling van de oude terminale attempt. De oude attempt
  `…successor.…run.1.59cab7d5` met haar oorspronkelijke `acceptance=false`,
  launchlimiet en bewijsstukken is ongemoeid bewaard; er wordt niet gearchreven
  dat de ontbrekende reviewhandler daarmee zou zijn gebouwd.

### 8.2 Acceptatie-equivalentie (uit bestaand bewijs)

| Aspect | Oud (successor-run 59cab7d5) | Nieuw (successor-2 run 519a148f) |
| --- | --- | --- |
| Programmadigest (run-gereserveerd) | `e310c96ad14e8d86c1400008c86dfce611c3ab71e3f14dd6e437631a51bef907` | `2383b3e12a13fad8cbdb0679130306fda99c6fd98b608be4fdb688acfbfe0963` |
| Criteria/config | `diagnostic-tests` (COMMAND) + `candidate-changed` (GIT_TREE_CHANGED); zelfde limieten/mutation_paths | identieke criteria, limieten en mutation_paths; enige inhoudelijke verschillen: programma-id/referentie, verify-first-instructie, gecorrigeerde acceptance-argv, profiel zonder model-pin |
| Interpreter | `/home/gebruiker/.cache/atlas-r-deploy/runtime-008/bin/python` (3.14.4, pytest 9.1.1) | dezelfde interpreter |
| cwd / rootdir | diagnostics-workspace | dezelfde workspace |
| Werkelijk geladen project_atlas | site-packages `project_atlas 2.0.0` (non-editable) — bewezen met `import project_atlas; __file__` | via argv `sys.path.insert(0,'src')`: workspace-`src` vóór site-packages |
| Te draaien tests | 3 genoemde focused bestanden | exact dezelfde 3 bestanden |
| Kandidaat | workspace @ base `03bc4459` + worker-delta | dezelfde code: worker voerde 0 wijzigingen door; `progress_fingerprint` identiek (`b4616f70…`) |
| Foutoutput die de defecten aantoont | recorded `acceptance_detail`: "unrecognized arguments: --cov=project_atlas …" (pytest-cov ontbreekt) | bestaande lokale run van de oude argv: `ModuleNotFoundError: prime_inference_proxy` (verkeerde importbinding) |
| Uitslag | acceptance=false (usage error, exit 4) | 73 passed in 8,64s + tree changed |

- **Coverage hoort niet tot het contract**: de acceptatie van de taak bestaat
  uit de twee checks hierboven; er is geen coverage-check of -threshold in het
  programma. De `--cov`-vlaggen kwamen uit de **geërfde** workspace-pyproject
  (`addopts`), niet uit de taakcriteria. Het wissen van addopts schakelt dus
  geen verplichte check uit; er is ook niets verzonnen om een eerder groen
  resultaat rood of groen te maken — de equivalentie volgt uit de recorded
  foutoutput plus dezelfde code en tests.
- **Resultpin**: geteste code = workspace HEAD `03bc4459c3b3…` (tree
  `474fd57a3226…`) plus worker-delta (`git diff`-hash `a31f6368a7e4…`,
  9 paden met per-bestand sha256 — waaronder proxy/test `ff7a44bc…`/`8bf9f7dd…`
  en relay `abe4f3b4…` dat buiten de claim valt). `be77e779` is en blijft de
  documentatiepin; identieke 73 uitslagen bewijzen op zichzelf geen gelijke
  code/criteriadekking — de dekking volgt uit de pin + identieke fingerprint.
  Niet-autuur-verdict: §7.5 IV PASS (auteur worker = codex-diagnostics-001;
  reviewer = deze operator-sessie). Geen suite-herhaling: alle checks droegen
  op bestaande traces/manifests.

### 8.3 Launch-/grantbinding en verbruik

- **Admissionreceipt**: enrollment `codex-diagnostics-001` (20:58:40Z,
  AUTHORIZED-OPERATOR) + assignment 2026-09-15T06:38:10Z naar successor-2
  (program-digest `2383b3e1…`); lease `…successor-2-…-1`, capability IMPLEMENT,
  status RELEASED na CERTIFIED. Executor: codex-adapterworker (geen
  verifierlaunch, geen modelvrije uitvoering).
- **Bevoegdheid**: gedekt door de ownerinstructie aan de vertrouwde operator
  van 2026-09-15 (voortzetting bootstrapketen). Het oorspronkelijke
  90-minutenvenster vanaf admission (20:58:40Z+90m) was verstreken op moment
  van dispatch — als feit geregistreerd, niet teruggedateerd of retroactief
  gelegitimeerd; de substantiële caps (1 worker, 1 launch, 5400 s, geen
  recursie, geen model-pin, geen providergrant) zijn aangehouden.
- **Verse state-root reset niets**: voorganger-state, -digests
  (`68277d7f…`, `e310c96a…`), terminale attempts (`88fd8f0e` FAILED,
  `59cab7d5` acceptance=false) en registry (`q-agent-009`) zijn ongewijzigd.
- **Verbruiksledger** (cached is deel van input, nooit erbovenop geteld):
  `88fd8f0e` = leeg (pre-worker mislukt); `59cab7d5` = input 2.477.957
  (cached 2.378.752), output 18.803; `519a148f` = input 488.204 (cached
  418.816), output 1.229. Onafhankelijke runs; som = input 2.966.161, output
  20.032; geen kostenpost verzonnen; codergebruik geboekt op de
  diagnosticstaakgrant, niet onder een IV-grant.

### 8.4 Schrijfscope-afwijking en disposition

- Werkelijk door de worker gewijzigd buiten de gedeclareerde paths:
  `docs/orchestration/program/evidence/prime-local-001-runtime-manifest.json`
  (één regel: `adapter_version` v1→v2; bestandsha `8a08269c…`). De lease ten
  tijde van de write kende alleen de 7 gedeclareerde paths — toestemming voor
  dit bestand ontbrak. Onveranderde freeze-hash (`2264052…`) en IV-PASS
  legitimeren deze write niet met terugwerkende kracht.
- Binnen een gedeclareerde file maar freeze-relevant: `ADAPTER_VERSION` v1→v2
  in `prime_agent.py`; patch- en upstream-constanten ongewijzigd; de
  toelatingspoort hangt aan de patch-hash, niet aan het versielabel.
- **Disposition (ownerbeslissing vereist, geen historische herschrijving)**:
  (a) behoud met afwijkingsnotitie (label matcht adapter-self-id v2), (b)
  owner-geautoriseerde targeted revert van de manifestregel in een toekomstige
  begrensde taak, of (c) afsplitsing. Eventuele latere toestemming werkt
  prospectief en wist de registratie hier niet.
- **Relay/pilot-WIP** (`scripts/prime-local-001-inference-relay.py`,
  `abe4f3b4…`): pre-existing parallel-lane materiaal, buiten de workerclaim;
  0 referenties in tests/src/worker-bestanden → geen invloed op de gebruikte
  test-/runtimebinding; ongemoeid gelaten.

### 8.5 Drie trace-diagnoses (inhoudelijk)

| Poging | Pin (sha256) | Records | Diagnose | Waargenomen | Plek in keten |
| --- | --- | ---: | --- | --- | --- |
| `kernel-bound-rpc-6` | `7207d095da8b…aa2c` | 639 | `no_structured_toolcall` | échte 1.7B-inferentie voltooid (Prime `agent_end`, 111,18 s, 2.803 tokens), alleen reasoning-text; geen gestructureerde ipython-call | model-responsfase; request/response compleet, geen tool-uitvoering bereikt |
| `kernel-bound-capability-1` | `00a458ab5583…a6a1` | 336 | `kernel_start_failure` | geldige gestructureerde ipython-call (`toolcall_end` regel 264), `tool_execution_start` (266), kernelstartfout (267), `tool_execution_end isError:true` (268) + gepersisteerd `toolResult` (270): `PRIME_AGENT_KERNEL_PYTHON` wees naar Python zonder current `prime-agent-runtime` | tool-uitvoering/kernelstart; call aanvaard, kernel startte niet |
| `kernel-bound-capability-2` | `12580324ebb6…be8` | 7 | `unknown` | connection reset; partieel transcript; `reasoning_effort:none`-correctie aanwezig; geen compleet assistant-antwoord | transport/responsfase, incompleet |

Bronartefacten: `…/atlas-prime-pilot.JF33Zo/evidence/<attempt>/<attempt>.prime-rpc.jsonl`
(vluchtige /tmp-locatie; de sha256-pins zijn de blijvende verwijzing).
Ontbrekende data blijft UNKNOWN; geen verzonnen hoofdoorzaak; geen nieuwe
Qwen-/Prime-capabilitycyclus.

### 8.6 Gerechtvaardigde taakstatus en archivering

- **Diagnosetaakacceptatie: gerechtvaardigd en bevestigd** — gedragen door
  run.1.519a148f + §8.2-equivalentie + §7.5 IV PASS. `CERTIFIED` geldt
  uitsluitend voor AS-PRIME-TOOLCALL-DIAGNOSTICS-001; het is geen
  productcertificering.
- **ATLAS-VERIFICATION-ROUTE-IMPLEMENT-001: gearchiveerd** als
  "overtaken-by-run.1.519a148f + equivalentiechecks" — niet gemarkeerd als
  uitgevoerd en niet als productgeaccepteerd; gebouwde routecode en evidence
  ongemoeid bewaard; heractivering vereist een nieuw ownerbesluit.
- **Open blijven afzonderlijk** (ongewijzigd uit §4): Prime-real-modeltoolcall,
  native modeldelegatie, coding-slice, exact-head CI op `913bc791`, canonieke
  kennisontvangst, deployment, menselijke IV.
- **Vervolg**: er is geen al-toegelaten vervolgwerk met werkelijk beschikbare
  executor én geldige grant over; dit dossiercommit is het checkpoint, hiermee
  stopt deze controle.

## 9. Addendum 2026-09-15 (3) — gerichte aanvulling van bewijsbindingen

Geen hercontrole en geen nieuwe launches; alleen ontbrekende bindingen uit
bestaande artefacts aangevuld.

- **Transcript-pins geverifieerd tegen de nog aanwezige evidence**
  (`/tmp/atlas-prime-pilot.JF33Zo/evidence/`, read-only, 2026-09-15): de drie
  `*.prime-rpc.jsonl` hashen exact gelijk aan de gepinde waarden —
  `7207d095…` (rpc-6), `00a458ab…` (capability-1), `12580324…` (capability-2).
  De volatile map kan verdwijnen; de pins blijven de verwijzing.
- **Request-zijde hard gemaakt**: de per-poging bewaarde
  `*.inference-audit.jsonl` (rpc-6: 1 regel; capability-1: 2; capability-2: 1)
  bevatten **geen** `"tools"`- en geen `"request"`-veld. Daarmee blijft
  "was het ipython-schema aangeboden?" voor rpc-6 en capability-2 **UNKNOWN**
  op basis van bewaard bewijs (geen verzonnen oorzaak). Voor capability-1 is
  het aanbod alleen indirect bewezen: de transcript bevat een geldige
  gestructureerde `ipython`-call, dus het schema is in díé sessie doorgestuurd.
- **Blob-pins van de gecertificeerde delta** (`git hash-object`, read-only),
  aanvullend op de sha256's uit §8.2: inventory-doc `22b3b262…`, manifest
  `1bcb9655…`, `prime_agent.py` `24f5e6aa…`, `control.py` `747e335a…`,
  control-test `835365c4…`, adapter-test `bc1fdb5f…`, relay (buiten claim)
  `469c5d89…`, proxy `49401567…`, proxy-test `d61fbdff…`; base HEAD `03bc4459…`
  / tree `474fd57a…`, delta-hash `a31f6368…` (ongewijzigd geverifieerd).
- **Ledgerclarificatie t.b.v. cumulatieven**: de interactive lane rapporteerde
  zelf 181.597 tokens (bootstrap-afronding, 2026-09-14 ~21:15Z) en 132.859
  (2026-09-15 ~06:23Z). Dat zijn **zelfgerapporteerde waarden van de eigen
  sessie van die lane**, geen supervisor-attempts; zij worden apart geregistreerd
  en nooit opgeteld bij de drie attempt-ledgers uit §8.3 (aantoonbaar
  onafhankelijke runs). Geen dubbeltelling; geen Qwen-budget aan geraakt.
- **Onveranderd**: gecertificeerde workspace (delta-hash `a31f6368…`, 9 paden),
  taak CERTIFIED, alle §8-conclusies. Parallelle WIP (o.a. de routecode van de
  andere lane) ongemoeid; geen enkel proces beëindigd.
