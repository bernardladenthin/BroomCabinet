# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""German income tax return (Einkommensteuererklärung) as data: one YAML file per return.

    from taxde import rechne
    ergebnis = rechne("Steuererklärung 2025.yaml")

Command line: python pytaxde.py "Steuererklärung 2025.yaml" [--details] [--belege]

Identifiers, YAML keys and output stay German on purpose: they have to match the ELSTER forms
(Anlage N, Werbungskosten, ...). No warranty, no tax advice.
"""
from .rechner import Eintrag, Ergebnis, Rechner, belege, belege_pruefen, rechne, zumutbare_belastung  # noqa: F401
