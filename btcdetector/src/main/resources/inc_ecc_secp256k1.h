/**
 * Author......: See docs/credits.txt
 * License.....: MIT
 */

#ifndef _INC_ECC_SECP256K1_H
#define _INC_ECC_SECP256K1_H

// y^2 = x^3 + ax + b with a = 0 and b = 7 => y^2 = x^3 + 7:

#define SECP256K1_B 7

// finite field Fp
#define SECP256K1_P0 0xfffffc2f
#define SECP256K1_P1 0xfffffffe
#define SECP256K1_P2 0xffffffff
#define SECP256K1_P3 0xffffffff
#define SECP256K1_P4 0xffffffff
#define SECP256K1_P5 0xffffffff
#define SECP256K1_P6 0xffffffff
#define SECP256K1_P7 0xffffffff

// prime order N
#define SECP256K1_N0 0xd0364141
#define SECP256K1_N1 0xbfd25e8c
#define SECP256K1_N2 0xaf48a03b
#define SECP256K1_N3 0xbaaedce6
#define SECP256K1_N4 0xfffffffe
#define SECP256K1_N5 0xffffffff
#define SECP256K1_N6 0xffffffff
#define SECP256K1_N7 0xffffffff

// the base point G in compressed form for transform_public
// G = 02 79BE667E F9DCBBAC 55A06295 CE870B07 029BFCDB 2DCE28D9 59F2815B 16F81798
#define SECP256K1_G_PARITY 0x00000002
#define SECP256K1_G0 0x16f81798
#define SECP256K1_G1 0x59f2815b
#define SECP256K1_G2 0x2dce28d9
#define SECP256K1_G3 0x029bfcdb
#define SECP256K1_G4 0xce870b07
#define SECP256K1_G5 0x55a06295
#define SECP256K1_G6 0xf9dcbbac
#define SECP256K1_G7 0x79be667e

// the base point G in compressed form for parse_public
// parity and reversed byte/char (8 bit) byte order
#define SECP256K1_G_STRING0 0x66be7902
#define SECP256K1_G_STRING1 0xbbdcf97e
#define SECP256K1_G_STRING2 0x62a055ac
#define SECP256K1_G_STRING3 0x0b87ce95
#define SECP256K1_G_STRING4 0xfc9b0207
#define SECP256K1_G_STRING5 0x28ce2ddb
#define SECP256K1_G_STRING6 0x81f259d9
#define SECP256K1_G_STRING7 0x17f8165b
#define SECP256K1_G_STRING8 0x00000098

#define SECP256K1_PRE_COMPUTED_XY_SIZE 96
#define SECP256K1_NAF_SIZE 33 // 32+1, we need one extra slot

#define PUBLIC_KEY_LENGTH_WITHOUT_PARITY 8
// 8+1 to make room for the parity
#define PUBLIC_KEY_LENGTH_WITH_PARITY 9

// (32*8 == 256)
#define PRIVATE_KEY_LENGTH 8

typedef struct secp256k1
{
  u32 xy[SECP256K1_PRE_COMPUTED_XY_SIZE]; // pre-computed points: (x1,y1,-y1),(x3,y3,-y3),(x5,y5,-y5),(x7,y7,-y7)

} secp256k1_t;


DECLSPEC u32  transform_public (secp256k1_t *r, const u32 *x, const u32 first_byte);
DECLSPEC u32  parse_public (secp256k1_t *r, const u32 *k);

DECLSPEC void point_mul (u32 *r, const u32 *k, GLOBAL_AS const secp256k1_t *tmps);

#endif // _INC_ECC_SECP256K1_H
