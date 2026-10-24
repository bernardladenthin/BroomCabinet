<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Third-party license review

This collection contains separately built Java/Python projects, not a single runtime graph.
Review each project independently, including JavaFX, JNA, JDBC drivers and bundled material.

## Finding BROOM-LIC-001: SevenForums registry configuration

| Field | Recorded assessment |
|---|---|
| Status | **Unresolved — assessment pending** |
| Scope | BroomCabinet only: 114 `.reg` files in `Platforms/Windows/FileAssociations/Windows7-Defaults/` and one in `Windows8-BatFile/` |
| Reviewed | 2026-10-24; all 115 file contents read and decoded, without importing them into Windows |
| Provenance | Repository attribution to Shawn Brink / SevenForums; 29 files also contain that attribution directly. Each file was not individually compared with an upstream download. |
| Technical content | Predominantly Microsoft Windows default registry values, file associations, shell commands, GUIDs and folder metadata. No substantial independent program logic identified. `Default_Drive.reg` includes seven declarative BitLocker context-menu conditions. |
| Open question | Whether any protectable third-party contribution exists in these particular files or their selection/arrangement, and whether a redistribution grant is needed for it. |
| License evidence | No explicit general redistribution grant was found in the referenced tutorial. Current forum terms grant publishing rights to the service provider; they do not establish a general third-party redistribution grant. This does not by itself establish infringement or copyright protection of the registry values. |
| Current decision | Retain the files and provenance markings while the assessment remains unresolved. No release blocker has been established from this finding. No assertion of clearance or license grant is made. |
| Revisit when | A specific protected contribution, applicable license, permission or substantive complaint is identified. Record the exact files and evidence before changing the assessment. |

`LICENSES/LicenseRef-SevenForums.txt` and the per-file `.license` sidecars remain
provenance documentation. They are not an Apache-2.0 grant or an approval.

This is a repository review record, not a scanner configuration. A scanner can encounter
the LicenseRef markings, but this Markdown record does not automatically create, resolve,
ignore or approve a FOSSA issue. No confirmed FOSSA issue ID is associated with this finding.

## Shared evidence

See [the workspace policy](https://github.com/bernardladenthin/workspace/blob/main/policies/dependency-license-review.md).
No public FOSSA project was confirmed for BroomCabinet. No approval of its independent
Java/Python dependencies or of its reference materials is implied by the shared policy.
