# coscarOS: Artcraft comparison and Austrian/EU review

Checked 24 October 2026 for the requested Austrian/EU assessment of the public source repository; updated for the coscarOS rename at commit `ee8e31e`. Published with the project owner's authorization. No private raw observations, credentials, contacts or vehicle recordings accompany this report. This is a source-backed engineering review and issue assessment, not a court determination, trademark clearance, patent search or legal opinion from counsel.

## Finding

Our documented observation-and-reimplementation method broadly resembles the method Artcraft describes. That supports an independent-functionality implementation; it does **not** establish that our deliberately close visual reproduction is lawful in every respect. The displayed product and repository are now named **coscarOS**; name clearance and GUI originality remain separate open questions. The defensible conclusion is conditional, not “Artcraft did it, therefore our clone is legal.”

## What Artcraft actually claims

The official [Crafting Apps page](https://getartcraft.com/apps) presents a suite of independently named creative/office tools, with multiple tools still marked alpha or in development. It is not evidence that the entire Adobe or Microsoft 365 product/service ecosystem was reproduced or legally approved.

[WordCraft](https://github.com/storytold/wordcraft) describes implementation from public specifications and observation. Its [agent policy](https://github.com/storytold/wordcraft/blob/main/AGENTS.md) expressly excludes copying/tracing proprietary assets and reading/disassembling the Word bundle, and requires asset attribution. [PhotoCraft's policy](https://github.com/storytold/photocraft/blob/main/AGENTS.md) likewise permits observing behavior/appearance while excluding proprietary code, shaders, profiles and assets. Its [attribution inventory](https://github.com/storytold/photocraft/blob/main/ATTRIBUTION.md) records source/license per asset. These are the projects' own statements and safeguards; the reviewed materials do not constitute judicial clearance.

## Austrian/EU legal baseline

- **Observation by an entitled user:** Austrian [UrhG §40d(3)(2) and (4)](https://www.ris.bka.gv.at/NormDokument.wxe?Abfrage=Bundesnormen&Gesetzesnummer=10001848&Paragraf=40d&ShowPrintPreview=True) permit studying operation to determine underlying ideas/principles during authorized use and make the specified rights non-waivable. Entitlement and the authorized acts still matter. This is not permission to redistribute the original software or protected assets.
- **Functionality versus expression:** [CJEU C-406/10, SAS Institute, judgment](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:62010CJ0406), particularly paragraphs 39–46 and the operative part, distinguishes functionality from protected program expression. It does not authorize taking protected source/object code or copying original manual expression.
- **The interface is a separate issue:** [CJEU C-393/09, BSA, judgment](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:62009CJ0393), paragraphs 42–51, recognizes possible copyright protection for an original GUI under ordinary copyright, even though it is not program expression under the Software Directive. Components dictated solely by technical function are distinguished from creative arrangements. Our use of code instead of screenshots does not by itself settle this question.
- **Decompilation is narrower:** [UrhG §40e](https://www.ris.bka.gv.at/eli/bgbl/1936/111/P40e/NOR12036608) is an interoperability exception with conditions and use restrictions, not general permission to create a visually identical competitor. Our stated method does not rely on proprietary decompilation.
- **Branding is independent:** [Markenschutzgesetz §10, current text](https://www.ris.bka.gv.at/Dokument.wxe?Abfrage=Bundesnormen&Dokumentnummer=NOR40209564&ShowPrintPreview=True) distinguishes exclusive trademark rights and qualifying identification/reference uses consistent with honest commercial practices. A product name and apparent endorsement need separate assessment. This review did not establish whether Hudiy has particular Austrian/EU registrations, reputation or other protected signs; no inference that an unregistered name is automatically free to use should be drawn.

## Repository comparison

| Issue | Evidence in this project | Assessment |
|---|---|---|
| Independent implementation | React/CSS interface, Python device service and our native host are source implementations. The default runtime is independent of proprietary Hudiy. Native code openly identifies its GPL protocol adaptation. | Supports independent reimplementation; this is not proof of every line's provenance. |
| Observation entitlement | The recorded workflow used the owner's running installation and publicly accessible documentation. | Owner authorization is recorded; original purchase/license entitlement and all accepted EULA terms were not independently examined. |
| Proprietary files | The historical 157-file tracked inventory at the initial audit and filename-history checks did not reveal proprietary binaries, a Hudiy source bundle or tracked raw research/vendor directories. Gallery captions identify our own app and synthetic fixtures. | Scoped checks, not a forensic comparison against proprietary source or every historical asset's provenance. Raw observations staying private does not itself license anything. |
| Clean-room separation | Policy prohibits proprietary source/assets. The same development process observed reference screens and implemented them. | Describe this precisely as black-box/observation-based reimplementation; do not claim a formally segregated two-team clean room. |
| Interface appearance | The stated goal included 1:1 reference screens, original gauge appearances, layout and visual conventions. Hudiy's [site](https://hudiy.eu/) itself describes Material 3 styling. | Shared generic Material conventions do not resolve copyright in a distinctive overall arrangement. A targeted visual originality review remains open. |
| Branding | The initial audit found “Hudiy recreation” and “Hudiy Marketplace” labels. The owner subsequently selected **coscarOS**; the app, native display names, installer, repository and update URLs were renamed, and the marketplace placeholder is now “coscarOS Extensions.” Historical attribution and stable compatibility IDs remain. | Rebranding and non-affiliation wording reduce the risk of apparent official affiliation; they do not establish trademark availability or remove any GUI rights. No formal name search/clearance has been completed. See [branding compatibility](BRANDING.md). |
| Third-party assets | Roboto and Material Symbols come from open-license npm packages, not extracted Hudiy assets. React, React DOM, Scheduler, Chart.js, its color helper and a Vite browser helper are used. | The original build omitted full dependency/font licenses from its distributed asset folder. This review adds a deterministic notice generator, copies the complete installed license texts/available NOTICE files into every build and adds an artifact regression check and About viewer. |
| Native licenses | Native GPL-3.0-or-later license and pinned protocol/submodule sources are identified in [native notices](../implementation/native/THIRD_PARTY.md); dashboard/backend sources retain MIT. | Public native binaries/images would require a complete corresponding-source and applicable notice/distribution compliance review. Private on-device source compilation is not equivalent to a public binary release. |

The [GNU license FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#UnchangedJustBinary) explains corresponding-source obligations when conveying binaries. The operative GPL-3.0 conditions are also available in the [native license, section 6](../implementation/native/LICENSE). A repository link/pin is useful provenance but is not, by itself, a complete binary-distribution compliance process. OS Qt/FFmpeg/libusb and their applicable licenses must also be considered for any redistributed image or appliance.

## Changes made and unresolved decisions

- [x] Compare primary Artcraft repositories/policies, Austrian statutes and relevant CJEU judgments.
- [x] Record the actual source/asset/branding findings and the limits of the review.
- [x] Add complete browser dependency/font notices to source and built assets, an About viewer and a build-artifact regression check.
- [x] Add explicit non-affiliation wording to About while retaining existing saved data and device identities.
- [x] Adopt **coscarOS** as the independent product/repository name and remove official-looking marketplace product labels.
- [ ] Complete an Austrian/EU trademark and other relevant name-rights clearance for coscarOS, including similar signs and relevant goods/services.
- [ ] Have distinctive copied visual arrangements assessed, and redesign protected/nonessential details or obtain permission where needed.
- [ ] Examine the original accepted license/entitlement evidence and any relevant design rights, unfair-competition, confidentiality, patent and protocol/certification constraints. Public distribution can implicate additional jurisdictions.
- [ ] Before publishing native binaries/images or selling devices, prepare and verify complete corresponding source, dependency notices and any required installation information.

No part of this report establishes that Artcraft has permission from Adobe/Microsoft or that the original Hudiy rights holder has approved this project. Obtain Austrian IP counsel's review before treating the unresolved public-release issues as cleared.

## Public documentation and publication boundary

The [legal index](../LEGAL.md) connects this assessment with the [development policy](../CLEAN_ROOM_POLICY.md), [asset and dependency provenance](ASSET_PROVENANCE.md), [complete browser notices](../implementation/dashboard/public/THIRD_PARTY_NOTICES.txt), [native notices](../implementation/native/THIRD_PARTY.md) and [branding migration](BRANDING.md). These records describe the implementation and outstanding review work. They do not grant rights owned by someone else or turn an unresolved issue into a completed clearance.

Only the public assessment is published. Raw reference captures, original license/account evidence, private contact/device/network data and vehicle logs remain excluded. If those materials are needed by counsel, provide them privately through an authorized channel. This report is a scoped assessment of documented development and available sources, not a guarantee that every current or future contribution has been independently audited.
