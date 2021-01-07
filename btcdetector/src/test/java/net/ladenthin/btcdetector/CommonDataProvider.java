// @formatter:off
/**
 * Copyright 2020 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
// @formatter:on
package net.ladenthin.btcdetector;

import com.tngtech.java.junit.dataprovider.DataProvider;

public class CommonDataProvider {

    /**
     * For {@link #bitSizesLowerThan25()}.
     */
    public final static String DATA_PROVIDER_BIT_SIZES_LOWER_THAN_25 = "bitSizesLowerThan25";

    @DataProvider
    public static Object[][] bitSizesLowerThan25() {
        return new Object[][]{
            {1},
            {2},
            {3},
            {4},
            {5},
            {6},
            {7},
            {8},
            {9},
            {10},
            {11},
            {12},
            {13},
            {14},
            {15},
            {16},
            {17},
            {18},
            {19},
            {20},
            {21},
            {22},
            {23},
            {net.ladenthin.btcdetector.OpenClTask.MAX_GRID_NUM_BITS}
        };
    }
    
    /**
     * For {@link #compressedAndAmount()}.
     */
    public final static String DATA_PROVIDER_COMPRESSED_AND_STATIC_AMOUNT = "compressedAndStaticAmount";

    @DataProvider
    public static Object[][] compressedAndStaticAmount() {
        return new Object[][]{
            {true, true},
            {false, true},
            {true, false},
            {false, false}
        };
    }
    
    /**
     * For {@link #staticAmount()}.
     */
    public final static String DATA_PROVIDER_STATIC_AMOUNT = "staticAmount";

    @DataProvider
    public static Object[][] staticAmount() {
        return new Object[][]{
            {true},
            {false},
        };
    }
    
    /**
     * For {@link #bitcoinInvalidP2WPKHAddresses()}.
     */
    public final static String DATA_PROVIDER_BITCOIN_INVALID_P2WPKH_ADDRESSES = "bitcoinInvalidP2WPKHAddresses";

    @DataProvider
    public static Object[][] bitcoinInvalidP2WPKHAddresses() {
        return new Object[][]{
            {"bc1pmfr3p9j00pfxjh0zmgp99y8zftmd3s5pmedqhyptwy6lm87hf5ss52r5n8"},
            {"bc1pqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqs3wf0qm"},
            {"bc1zqyqsywvzqe"},
        };
    }
    
    /**
     * For {@link #bitcoinAddressesCorrectBase58()}.
     * A correct base58 format should be parsed anyway.
     */
    public final static String DATA_PROVIDER_BITCOIN_ADDRESSES_CORRECT_BASE_58 = "bitcoinAddressesCorrectBase58";

    @DataProvider
    public static Object[][] bitcoinAddressesCorrectBase58() {
        return new Object[][]{
            {"1WrongAddressFormat","01667b78604490800f88b15c77a5000000000000"},
            {"1WrongAddressFormat2","5137f945cf88bd0384f82ef31b63000000000000"},
            {"1Wrong1Address2Format3","042b438790b52de2b8235712dbd6e2e400000000"},
        };
    }
    
    /**
     * For {@link #bitcoinAddressesInvalidBase58()}.
     * A invalid base58 format can't be read.
     */
    public final static String DATA_PROVIDER_BITCOIN_ADDRESSES_INVALID_BASE_58 = "bitcoinAddressesInvalidBase58";

    @DataProvider
    public static Object[][] bitcoinAddressesInvalidBase58() {
        return new Object[][]{
            {"1Wr0ngAddressFormat"},
            {"1WrongAddressFormat0"},
            {"1WrongIAddressFormat"},
            {"1WronglAddressFormat"},
        };
    }
    
    /**
     * For {@link #bitcoinCashAddressesChecksumInvalid()}.
     * TODO: I don't know if this is right. It seems like it's a base58 format.
     * I've asked Blockchair and they've answered: "The addresses you listed are for internal purposes.".
     */
    public final static String DATA_PROVIDER_BITCOIN_CASH_ADDRESSES_CHECKSUM_INVALID = "bitcoinCashAddressesChecksumInvalid";

    @DataProvider
    public static Object[][] bitcoinCashAddressesChecksumInvalid() {
        return new Object[][]{
            {"dSn3treXZQfJRktvoApJKM","27225957c54a53b10e4f4e00b2562af400000000"},
            {"bq2ZTwe8pt3hyCuy5MudVG","1a0b606a1f1de7a130aae81dc66c665700000000"},
            {"W6xvVjvtRobnz9dDdjEugV","ae340f03861fd08558312b97e7926a0000000000"},
            {"N1JULkP6RqW3LcbpWvgryV","1aadd1f5457c0f8c08763e55745ff80000000000"},
            {"8cE2K6rzN1dVjQXfX3SFcZ","9b072e05be8ff2d1a26e73c694644e0000000000"},
            {"kGuKp2vSFzNQ5SJftineWu","5e715d6cc9f93ed922579fd06c47017200000000"},
            {"5QmydJKnwKPJb8m1zEQpUV","b661051dd8b1893dd2c10fae9c00de0000000000"},
            {"FyXF2p5s8qbonKTuB4MWFr","443ac752c9c5e5445abfe6898dad010000000000"},
            {"rWMr7gq4bDKs3T1TgWpTrg","90e9360283cee7ba62e81fe2ef67dcf100000000"},
            {"d6qya271t3cYzW8qEEui4E","2459e48a008f3c73c00f9f6e9b24ff0f00000000"},
        };
    }
    
    /**
     * For {@link #bitcoinCashAddressesInternalPurpose()}.
     * TODO: I don't know if this is right. It seems like it's a hex format.
     * I've asked Blockchair and they've answered: "The addresses you listed are for internal purposes.".
     */
    public final static String DATA_PROVIDER_BITCOIN_CASH_ADDRESSES_INTERNAL_PURPOSE = "bitcoinCashAddressesInternalPurpose";

    @DataProvider
    public static Object[][] bitcoinCashAddressesInternalPurpose() {
        return new Object[][]{
            {"d-32551cbc0d16a34c5995b4057c3f027c"},
            {"d-29a0bd5b4cfbb05b493a11e0b69cedcc"},
            {"d-732cbc077831c75aba49f95eb629bc32"},
            {"d-f92fe84dd1620a12daea311393b37549"},
            {"d-ca0cf82e6bd2261f3a648a06090dc815"},
        };
    }
}
