/*
// example private key (in)
// hex: 68e23530deb6d5011ab56d8ad9f7b4a3b424f1112f08606357497495929f72dc
// decimal: 47440210799387980664936216788675555637818488436833759923669526136462528967388
// WiF
// to generate the public key (out)
// 025d99d81d9e731e0d7eebd1c858b1155da7981b1f0a16d322a361f8b589ad2e3b
// hex:
k_local[7] = 0x68e23530;
k_local[6] = 0xdeb6d501;
k_local[5] = 0x1ab56d8a;
k_local[4] = 0xd9f7b4a3;
k_local[3] = 0xb424f111;
k_local[2] = 0x2f086063;
k_local[1] = 0x57497495;
k_local[0] = 0x929f72dc;
*/

__kernel void generateKeysKernel_parse_public(__global u32 *r, __global const u32 *k)
{
    u32 g_local[PUBLIC_KEY_LENGTH_WITH_PARITY];
    u32 r_local[PUBLIC_KEY_LENGTH_WITH_PARITY];
    u32 k_local[PRIVATE_KEY_LENGTH];
    secp256k1_t g_xy_local;

    g_local[0] = SECP256K1_G_STRING0;
    g_local[1] = SECP256K1_G_STRING1;
    g_local[2] = SECP256K1_G_STRING2;
    g_local[3] = SECP256K1_G_STRING3;
    g_local[4] = SECP256K1_G_STRING4;
    g_local[5] = SECP256K1_G_STRING5;
    g_local[6] = SECP256K1_G_STRING6;
    g_local[7] = SECP256K1_G_STRING7;
    g_local[8] = SECP256K1_G_STRING8;

    // global to local
    k_local[0] = k[0];
    k_local[1] = k[1];
    k_local[2] = k[2];
    k_local[3] = k[3];
    k_local[4] = k[4];
    k_local[5] = k[5];
    k_local[6] = k[6];
    k_local[7] = k[7];
    
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
}

__kernel void generateKeysKernel_transform_public(__global u32 *r, __global const u32 *k)
{
    u32 g_local[PUBLIC_KEY_LENGTH_WITHOUT_PARITY];
    u32 r_local[PUBLIC_KEY_LENGTH_WITH_PARITY];
    u32 k_local[PRIVATE_KEY_LENGTH];
    secp256k1_t g_xy_local;
    
    g_local[0] = SECP256K1_G0;
    g_local[1] = SECP256K1_G1;
    g_local[2] = SECP256K1_G2;
    g_local[3] = SECP256K1_G3;
    g_local[4] = SECP256K1_G4;
    g_local[5] = SECP256K1_G5;
    g_local[6] = SECP256K1_G6;
    g_local[7] = SECP256K1_G7;

    // global to local
    k_local[0] = k[0];
    k_local[1] = k[1];
    k_local[2] = k[2];
    k_local[3] = k[3];
    k_local[4] = k[4];
    k_local[5] = k[5];
    k_local[6] = k[6];
    k_local[7] = k[7];
    
    const u32 first_byte = SECP256K1_G_PARITY & 0xff;
    transform_public(&g_xy_local, g_local, first_byte);
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
}

__kernel void generateKeysKernel_transform_public_grid(__global u32 *r, __global const u32 *k)
{
    u32 g_local[PUBLIC_KEY_LENGTH_WITHOUT_PARITY];
    u32 r_local[PUBLIC_KEY_LENGTH_WITH_PARITY];
    u32 k_local[PRIVATE_KEY_LENGTH];
    secp256k1_t g_xy_local;
    
    
    // get_global_id(dim) where dim is the dimension index (0 for first, 1 for second dimension etc.)
    // The above call is equivalent to get_local_size(dim)*get_group_id(dim) + get_local_id(dim)
    size_t global_id = get_global_id(0);
    
    //int local_id = get_local_id(0);
    //int local_size = get_local_size(0);
    
    g_local[0] = SECP256K1_G0;
    g_local[1] = SECP256K1_G1;
    g_local[2] = SECP256K1_G2;
    g_local[3] = SECP256K1_G3;
    g_local[4] = SECP256K1_G4;
    g_local[5] = SECP256K1_G5;
    g_local[6] = SECP256K1_G6;
    g_local[7] = SECP256K1_G7;

    // global to local
    int k_offset = PRIVATE_KEY_LENGTH * global_id;
    k_local[0] = k[k_offset+0];
    k_local[1] = k[k_offset+1];
    k_local[2] = k[k_offset+2];
    k_local[3] = k[k_offset+3];
    k_local[4] = k[k_offset+4];
    k_local[5] = k[k_offset+5];
    k_local[6] = k[k_offset+6];
    k_local[7] = k[k_offset+7];
    
    const u32 first_byte = SECP256K1_G_PARITY & 0xff;
    transform_public(&g_xy_local, g_local, first_byte);
    point_mul(r_local, k_local, &g_xy_local);

    // local to global
    int r_offset = PUBLIC_KEY_LENGTH_WITH_PARITY * global_id;
    r[r_offset+0] = r_local[0];
    r[r_offset+1] = r_local[1];
    r[r_offset+2] = r_local[2];
    r[r_offset+3] = r_local[3];
    r[r_offset+4] = r_local[4];
    r[r_offset+5] = r_local[5];
    r[r_offset+6] = r_local[6];
    r[r_offset+7] = r_local[7];
    r[r_offset+8] = r_local[8];
}

__kernel void test_kernel_do_nothing(__global u32 *r, __global const u32 *k)
{
}
