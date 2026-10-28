"""cutcord -- reference implementation for the Phase-3 evaluation.

Two schemes on the same curve (BN254 via py_ecc), so measured differences come from
the protocol design and not from the library:

* ``base``  -- Tan, Zheng & Vijayakumar (IEEE T-ITS 2023), Section IV, as printed;
* ``ours``  -- "Cutting the Cord": C1 (UAV tier), C2 (vehicle tier), C3 (handover).
"""
