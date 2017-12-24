{
    "command": "ProbeAddressesOpenCL",
    "blockchainAnalysis" : {
        "blockchainDirectory" : "I:/Bitcoin/blocks",
        "lastAnalyzedBlockHashFile" : "lastAnalyzedBlockHash.txt",
        "printStatisticsEveryNSeconds" : 20,
        "lmdbConfigurationWrite" : {
            "lmdbDirectory" : "lmdb",
            "deleteEmptyAddresses" : true,
            "mapSizeInMiB" : 61440
        },
        "orphanedBlocks" : [
            "00000000000000000051196672c3f6efacbade6c0ce2e50131c0cef572b26da5",
            "000000000000000000114150040c6b7caead48a7432845aac037c3965109be7c",
            "0000000000000000000b040cdce388ee2ff443856ccfa4062afab1fb9447695c",
            "000000000000000000d0863b014f9c9b56d5706eba08bba78b1ab3b99b6338a4",
            "0000000000000000013ff08983d2881386fdd04e879e186d57ce4c8367ee17da",
            "0000000000000000018d0e4f7101731b9a260a560a4ffc969144fd5315cf3acd",
            "00000000000000000007bf9cd120a090a3150b7c78752451153cd3646040b577",
            "000000000000000000a017dc392ec54958275c1e885f2a91dd57d74e21c19e91",
            "000000000000000001abee9e5f3dde018b226e5518a1fdf962f544cbaf15716c",
            "000000000000000000f88c9a54b57679f36526d3cd8754974b5db7c9ee8b25d5",
            "000000000000000000c89a56fec1a04a5981e7f614e6ba2f877559fc2ef9e138",
            "0000000000000000013503d24a8c9b8001f663a4d5ea9f06f9f38d58805723ae",
            "000000000000000001e43a1b261fc531a502ea1294985282f357af352a284c7a",
            "000000000000000001f0edf2c095ea0265ef4e0c7de70f358eb3cb4ecd8324dd",
            "000000000000000000ad4d5b2828bbe0e44f31ad185f93dba642e37bc204d9a2",
            "0000000000000000016e953348d08f41daffb1f84dcdd547bd00300cffd6f1b1",
            "000000000000000001ca7d5e740c0cf0227216805e7bc19d770fc732547d9aa1",
            "000000000000000000602ebf82b74d4ba727a538f19e812d9802fdde5f49afe0",
            "0000000000000000003c6fe479122bfa4a9187493937af1734e1e5cd9f198ec7",
            "0000000000000000022c1fb7b29483974c632e1d6ea09a145595c59faf3cd747",
            "00000000000000000020f78cbc24abdf635f32b5d874b0e4cb26bbab2d307f7b",
            "000000000000000000618ba70b51a387bf82aad3abee5ea0367ed6d43a28230f",
            "0000000000000000009085be97279a7ab4d20e983be9cb20fe0c2e0d49313cdd",
            "0000000000000000002aa9b76bd75f7a1e8b2b6c4c58e2de62e400f54f2d8e17",
            "000000000000000002518dd0ce22f5c2a29a6e03257da71b0e93f8e2020f57aa"
        ]
    },
    "extractAddresses" : {
        "addressesFile" : "extractAddresses.txt",
        "lmdbConfigurationReadOnly" : {
            "lmdbDirectory" : "lmdb"
        }
    },
    "probeAddressesCPU" : {
        "addressesFiles" : ["extractAddresses.txt", "staticAddresses.txt"],
        "foundFile" : "found.txt",
        "nThreads" : 6,
        "printStatisticsEveryNSeconds" : 20,
        "selftestFirst" : false
    },
    "probeAddressesOpenCL" : {
    "addressesFiles" : ["extractAddresses.txt", "staticAddresses.txt"],
        "foundFile" : "found.txt",
        "printStatisticsEveryNSeconds" : 20,
        "selftestFirst" : false
    }
}
