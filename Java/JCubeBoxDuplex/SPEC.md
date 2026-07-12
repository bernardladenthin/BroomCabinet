<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Cube-Box Duplex (CBD) — Spezifikation v0.1

> **⚠️ Experimentell / Lehrzweck.** Diese Konstruktion hat **keine** öffentliche
> Kryptoanalyse durchlaufen. Nicht für echte Daten verwenden. Sie ist ein
> Design-Experiment für eine neuartige Struktureigenschaft, kein
> produktionsreifes Verfahren.

## 1. Ziele und die eine ehrliche Grenze

CBD verfolgt vier Eigenschaften:

| # | Eigenschaft | Umsetzung |
|---|---|---|
| D | **Nur vorwärts** | Ver- und Entschlüsseln laufen dieselbe Permutation `P` **vorwärts**. Es gibt keinen inversen Operator `P⁻¹`. |
| C | **Würfel-Box-Auswahlstrom** | In jeder Runde wird jede 64-Bit-Lane durch **eine von 16 bijektiven „Würfel-Boxen"** transformiert; der Index wird daten- **und** schlüsselabhängig gewählt. Die Sequenz der Box-Wahlen ist ein geheimer, vom Schlüssel getriebener Strom. |
| B | **All-or-Nothing + Anker** | Klartext-Rückkopplung verkettet jeden Block in den Zustand; der Startzustand wird zusätzlich aus dem **ersten Klartextblock** (dem „Anker") abgeleitet. |
| A | **Work-Faktor** | Pro Block wird `P` `W`-mal angewandt — ein einstellbarer Härte-Regler. |

**Die eine physikalische Grenze (bewusst so entworfen):** Echte *Compute*-Asymmetrie
(billig verschlüsseln, teuer entschlüsseln) ist ohne algebraische Falltür
unmöglich — und eine Falltür würde die Quantensicherheit zerstören (Shor). CBD
liefert stattdessen **Informations-Asymmetrie**: Entschlüsseln geht vorwärts wie
Verschlüsseln, **braucht aber mehr Information** — Schlüssel **+** Nonce **+** den
ersten Klartextblock. Ohne den Anker läuft der Zustand in die Irre und *nichts*
rekonstruiert sich. `W` ist ein *symmetrischer* Kostenfaktor (beide Seiten zahlen
ihn), analog zu Argon2/PBKDF-Iterationen.

## 2. Quantensicherheit

CBD hat keine algebraische Falltür — nur eine große, strukturlose symmetrische
Permutation über einen **512-Bit-Zustand**. Gegen solche Konstruktionen ist der
einzige bekannte Quanten-Hebel **Grover**, der die Sicherheit lediglich halbiert
(Schlüssel/Zustand verdoppeln genügt). Damit steht CBD in derselben Klasse wie
SHA-3/Keccak und Ascon — dem heute als post-quantum geltenden symmetrischen
Fundament. (Im Gegensatz zu RSA/ECC/secp256k1, die Shor bricht.)

## 3. Parameter

| Symbol | Wert | Bedeutung |
|---|---|---|
| `LANES` | 8 | 64-Bit-Lanes → 512-Bit-Zustand |
| `RATE_LANES` | 4 | Rate = 256 Bit; Kapazität = 256 Bit |
| `BLOCK_BYTES` | 32 | Blockgröße (= Rate in Bytes) |
| `ROUNDS` | 12 | Runden pro `P` |
| `NUM_BOXES` | 16 | Anzahl Würfel-Boxen (4-Bit-Selektor) |
| `TAG_BYTES` | 16 | Authentifizierungs-Tag |
| `NONCE_BYTES` | 16 | Nonce-Länge |
| `W` | ≥ 1 | Work-Faktor (Konstruktor-Parameter) |

## 4. Konstanten (nothing-up-my-sleeve)

Alle Box- und Rundenkonstanten werden **deterministisch** aus dem dokumentierten
SplitMix64-Seed `0x9E3779B97F4A7C15` erzeugt (nachvollziehbar, keine versteckten
Werte). Für jede Box `i`: `BOX_MUL[i]` (ungerade → Multiplikation mod 2⁶⁴ ist
bijektiv), `BOX_ROT[i] ∈ [1,63]`, `BOX_ADD[i]`. `RC[0..127]` sind Rundenkonstanten.

## 5. Bausteine

### 5.1 Würfel-Box (Bijektion auf 64 Bit)

```
box(i, x) = rotl(x · BOX_MUL[i], BOX_ROT[i]) ⊕ BOX_ADD[i]
```

Multiplikation mit ungeradem Faktor, Rotation und XOR sind je bijektiv → jede Box
ist umkehrbar (nötig, damit der Zustand keine Entropie verliert — auch wenn wir
nie invertieren).

### 5.2 Permutation `P(state, keyLanes)` — nur vorwärts

Für `r = 0 … ROUNDS-1`:

1. **Würfel-Box-Schicht (der Auswahlstrom).** Für jede Lane `j` wird der Selektor
   aus *anderen* Lanes + Rundenkonstante + Schlüssel-Lane gebildet:
   ```
   sel[j] = ( (state[(j+1) mod 8] >>> 5)
            ⊕ (state[(j+5) mod 8] >>> 33)
            ⊕ RC[(r·8+j) mod 128]
            ⊕ keyLanes[j] ) mod 16
   ```
   Anschließend `state[j] = box(sel[j], state[j])`.
   → *Welche* Box eine Lane trifft, hängt von Daten **und** Schlüssel ab.
2. **Lineare Diffusion.** `t[j] = state[j] ⊕ rotl(state[(j+7) mod 8],7) ⊕ rotl(state[(j+2) mod 8],31)`.
3. **Lane-Rotation + Rundenkonstante.** `state[j] = t[(j+3) mod 8] ⊕ RC[(r+j) mod 128]`.

### 5.3 Sponge-Hash / Key-Schedule

Ein schlüsselloser Sponge (keyLanes = 0) mit `10*`-Padding und Domain-Trennung
liefert `deriveKeyLanes(key)` und `hashLanes(nonce/anchor)`.

## 6. Ablauf

### 6.1 Init

```
keyLanes = deriveKeyLanes(key)
state    = 0
state   ⊕= hashLanes(nonce);      state = P(state, keyLanes)
state   ⊕= hashLanes(block0);     state = P(state, keyLanes)   # block0 = Anker
```

### 6.2 Verschlüsseln (pro Block i)

```
Z_i        = state[0..3]                 # Keystream = Rate
C_i        = M_i ⊕ Z_i
state[0..3] ⊕= M_i                        # Klartext-Rückkopplung (All-or-Nothing)
state[4]   ⊕= i                          # Block-Domain-Trennung
wiederhole W×: state = P(state, keyLanes)
```
Abschluss: `state[7] ⊕= 0x8000…; P(...); TAG = state[0..1]`.

Paket: `[len(8) ‖ nonce(16) ‖ C_0…C_n ‖ TAG(16)]`.

### 6.3 Entschlüsseln

Benötigt `key`, `nonce` **und** den Anker (erste ≤ 32 Klartext-Bytes). Identischer
Vorwärtslauf: `M_i = C_i ⊕ Z_i`, Rückkopplung, Work-Faktor. Danach zwei Prüfungen:
**Anker-Check** (rekonstruierter erster Block == gelieferter Anker) und
**Tag-Check** (konstante Zeit). Ein falscher Schlüssel, ein falscher Anker oder ein
einziges verändertes Ciphertext-Byte lässt beide Prüfungen scheitern.

## 7. Bekannte Grenzen / offene Kryptoanalyse

- **Kein Sicherheitsbeweis.** Datenabhängige Box-Auswahl ist attraktiv, aber
  klassisch heikel (Differential-/Timing-Angriffe). Genau hier müsste eine echte
  Analyse ansetzen.
- **Timing-Seitenkanäle:** die Box-Auswahl ist datenabhängig; eine constant-time-
  Umsetzung müsste alle 16 Boxen rechnen und maskiert auswählen.
- **Rundenzahl `ROUNDS=12`** und die Diffusionsschicht sind ungetunt — sie
  bestehen den Avalanche-Selbsttest (~0.5), aber das ersetzt keine Analyse.
- **Nonce-Wiederverwendung** bricht die Vertraulichkeit (wie bei jedem Stream-XOR).

## 8. Selbsttest

`net.ladenthin.cbd.Demo` verifiziert: Round-Trip, Anker-Pflicht, Falsch-Schlüssel-
Ablehnung, Manipulations-Ablehnung, Keystream-Avalanche ≈ 0.5, Nonce-Wirkung und
leeren Klartext.
