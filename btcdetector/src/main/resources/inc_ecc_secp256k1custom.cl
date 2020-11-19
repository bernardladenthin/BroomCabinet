// #################### direct test
// test an address
// 68e23530deb6d5011ab56d8ad9f7b4a3b424f1112f08606357497495929f72dc
/*
k_local[0] = 0x68e23530;
k_local[1] = 0xdeb6d501;
k_local[2] = 0x1ab56d8a;
k_local[3] = 0xd9f7b4a3;
k_local[4] = 0xb424f111;
k_local[5] = 0x2f086063;
k_local[6] = 0x57497495;
k_local[7] = 0x929f72dc;
*/
// test an address up/down
// 68e23530deb6d5011ab56d8ad9f7b4a3b424f1112f08606357497495929f72dc
/*
k_local[7] = 0x68e23530;
k_local[6] = 0xdeb6d501;
k_local[5] = 0x1ab56d8a;
k_local[4] = 0xd9f7b4a3;
k_local[3] = 0xb424f111;
k_local[2] = 0x2f086063;
k_local[1] = 0x57497495;
k_local[0] = 0x929f72dc;
*/
// test an address swap endian
// 68e23530deb6d5011ab56d8ad9f7b4a3b424f1112f08606357497495929f72dc
/*
k_local[0] = 0x3035e268;
k_local[1] = 0x01d5b6de;
k_local[2] = 0x8a6db51a;
k_local[3] = 0xa3b4f7d9;
k_local[4] = 0x11f124b4;
k_local[5] = 0x6360082f;
k_local[6] = 0x95744957;
k_local[7] = 0xdc729f92;
*/
// #################### 

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


// the base point G in compressed form
// front align
/*
#define SECP256K1_G0 0x0279be66
#define SECP256K1_G1 0x7ef9dcbb
#define SECP256K1_G2 0xac55a062
#define SECP256K1_G3 0x95ce870b
#define SECP256K1_G4 0x07029bfc
#define SECP256K1_G5 0xdb2dce28
#define SECP256K1_G6 0xd959f281
#define SECP256K1_G7 0x5b16f817
#define SECP256K1_G8 0x98000000
*/

//
// swap endian
/*
#define SECP256K1_G0 0x66BE7902
#define SECP256K1_G1 0xBBDCF97E
#define SECP256K1_G2 0x62A055AC
#define SECP256K1_G3 0x0B87CE95
#define SECP256K1_G4 0xFC9B0207
#define SECP256K1_G5 0x28CE2DDB
#define SECP256K1_G6 0x81F259D9
#define SECP256K1_G7 0x17F8165B
#define SECP256K1_G8 0x00000098
*/

__kernel void generateKeysKernel_parse_public(__global u32 *r, __global const u32 *k)
{
    u32 g_local[PUBLIC_KEY_LENGTH_WITH_PARITY];
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
    
    g_local[0] = SECP256K1_G1;
    g_local[1] = SECP256K1_G2;
    g_local[2] = SECP256K1_G3;
    g_local[3] = SECP256K1_G4;
    g_local[4] = SECP256K1_G5;
    g_local[5] = SECP256K1_G6;
    g_local[6] = SECP256K1_G7;
    g_local[7] = SECP256K1_G8;

    // global to local
    k_local[0] = k[0];
    k_local[1] = k[1];
    k_local[2] = k[2];
    k_local[3] = k[3];
    k_local[4] = k[4];
    k_local[5] = k[5];
    k_local[6] = k[6];
    k_local[7] = k[7];
    
    const u32 first_byte = SECP256K1_G0 & 0xff;
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

__kernel void test_convert_to_window_naf(__global u32 *wnaf_global, __global u32 *loop_start_global, __global const u32 *k_global)
{
    u32 wnaf_local[SECP256K1_NAF_SIZE];
    u32 k_local[PRIVATE_KEY_LENGTH];

    // global to local
    for(int i=0; i < PRIVATE_KEY_LENGTH; i++) {
        k_local[i] = k_global[i];
    }

    int loop_start_local = convert_to_window_naf(wnaf_local, k_local);
    
    // local to global
    loop_start_global[0] = loop_start_local;

    for(int i=0; i < SECP256K1_NAF_SIZE; i++) {
        wnaf_global[i] = wnaf_local[i];
    }
}


__kernel void test_parse_public_g(__global u32 *xy_global)
{
    u32 g_local[PUBLIC_KEY_LENGTH_WITH_PARITY];
    secp256k1_t xy_pre_computed_local;
    
    g_local[0] = SECP256K1_G0;
    g_local[1] = SECP256K1_G1;
    g_local[2] = SECP256K1_G2;
    g_local[3] = SECP256K1_G3;
    g_local[4] = SECP256K1_G4;
    g_local[5] = SECP256K1_G5;
    g_local[6] = SECP256K1_G6;
    g_local[7] = SECP256K1_G7;
    g_local[8] = SECP256K1_G8;
    
    parse_public(&xy_pre_computed_local, g_local);
    
    for(int i=0; i < SECP256K1_PRE_COMPUTED_XY_SIZE; i++) {
        xy_global[i] = xy_pre_computed_local.xy[i];
    }
}

__kernel void test_parse_public(__global u32 *xy_global, __global const u32 *public_address_global)
{
    u32 public_address_local[PUBLIC_KEY_LENGTH_WITH_PARITY];
    secp256k1_t xy_pre_computed_local;

    for(int i=0; i < PUBLIC_KEY_LENGTH_WITH_PARITY; i++) {
        public_address_local[i] = public_address_global[i];
    }
    
    /*
    g_local[0] = SECP256K1_G0;
    g_local[1] = SECP256K1_G1;
    g_local[2] = SECP256K1_G2;
    g_local[3] = SECP256K1_G3;
    g_local[4] = SECP256K1_G4;
    g_local[5] = SECP256K1_G5;
    g_local[6] = SECP256K1_G6;
    g_local[7] = SECP256K1_G7;
    g_local[8] = SECP256K1_G8;
    */
    
    parse_public(&xy_pre_computed_local, public_address_local);
    
    for(int i=0; i < SECP256K1_PRE_COMPUTED_XY_SIZE; i++) {
        xy_global[i] = xy_pre_computed_local.xy[i];
    }
}
