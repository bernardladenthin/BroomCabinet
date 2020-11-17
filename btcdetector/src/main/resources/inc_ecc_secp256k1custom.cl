// 8+1 to make room for the parity
#define KEY_LENGTH_WITH_PARITY 9
// (32*8 == 256)
#define PRIVATE_KEY_LENGTH 8

// the base point G in compressed form
#define SECP256K1_G0 0x00000002
#define SECP256K1_G1 0x79be667e
#define SECP256K1_G2 0xf9dcbbac
#define SECP256K1_G3 0x55a06295
#define SECP256K1_G4 0xce870b07
#define SECP256K1_G5 0x029bfcdb
#define SECP256K1_G6 0x2dce28d9
#define SECP256K1_G7 0x59f2815b
#define SECP256K1_G8 0x16f81798

__kernel void generateKeysKernel(__global u32 *r, __global const u32 *k)
{
    u32 g_local[KEY_LENGTH_WITH_PARITY];
    u32 r_local[KEY_LENGTH_WITH_PARITY];
    u32 k_local[PRIVATE_KEY_LENGTH];
    u32 u32naf_local[32+1];
    secp256k1_t g_xy_local;

    g_local[0] = SECP256K1_G0;
    g_local[1] = SECP256K1_G1;
    g_local[2] = SECP256K1_G2;
    g_local[3] = SECP256K1_G3;
    g_local[4] = SECP256K1_G4;
    g_local[5] = SECP256K1_G5;
    g_local[6] = SECP256K1_G6;
    g_local[7] = SECP256K1_G7;
    g_local[8] = SECP256K1_G8;

    // global to local
    k_local[0] = k[0];
    k_local[1] = k[1];
    k_local[2] = k[2];
    k_local[3] = k[3];
    k_local[4] = k[4];
    k_local[5] = k[5];
    k_local[6] = k[6];
    k_local[7] = k[7];
    
    /*
    // test an address
    // 68e23530deb6d5011ab56d8ad9f7b4a3b424f1112f08606357497495929f72dc
    k_local[0] = 0x68e23530;
    k_local[1] = 0xdeb6d501;
    k_local[2] = 0x1ab56d8a;
    k_local[3] = 0xd9f7b4a3;
    k_local[4] = 0xb424f111;
    k_local[5] = 0x2f086063;
    k_local[6] = 0x57497495;
    k_local[7] = 0x929f72dc;
    */

    parse_public(&g_xy_local, g_local);
    point_mul(r_local, k_local, &g_xy_local);

    // local to global
    r[0] = r_local[0];
    r[1] = r_local[1];
    r[2] = r_local[2];
    r[3] = r_local[3];
    r[4] = r_local[4];
    r[5] = r_local[5];
    r[6] = r_local[6];
    r[7] = r_local[7];
    r[8] = r_local[8];

    /*
    // test for readBuffer
    r[0] = SECP256K1_G0;
    r[1] = SECP256K1_G1;
    r[2] = SECP256K1_G2;
    r[3] = SECP256K1_G3;
    r[4] = SECP256K1_G4;
    r[5] = SECP256K1_G5;
    r[6] = SECP256K1_G6;
    r[7] = SECP256K1_G7;
    r[8] = SECP256K1_G8;
    */
    /*
    // test for readbuffer    
    r[0] = g_xy_local.xy[0];
    r[1] = g_xy_local.xy[1];
    r[2] = g_xy_local.xy[2];
    r[3] = g_xy_local.xy[3];
    r[4] = g_xy_local.xy[4];
    r[5] = g_xy_local.xy[5];
    r[6] = g_xy_local.xy[6];
    r[7] = g_xy_local.xy[7];
    r[8] = g_xy_local.xy[8];
    */
    /*
    // test for convert_to_window_naf
    int loop_start = convert_to_window_naf(u32naf_local, k_local);
    r[0] = loop_start;
    r[1] = u32naf_local[0];
    r[2] = u32naf_local[1];
    r[3] = u32naf_local[2];
    r[4] = u32naf_local[3];
    r[5] = u32naf_local[4];
    r[6] = u32naf_local[5];
    r[7] = u32naf_local[6];
    r[8] = u32naf_local[7];
    */
}
