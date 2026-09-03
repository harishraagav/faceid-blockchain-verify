// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title FaceMatchRegistry
/// @notice Minimal on-chain registry for HH Goa 2026 Task 3. Anchors the
/// SHA-256 hash of a face-match record (see src/utils.py) on-chain,
/// emitting an event so ALL records ever submitted can be queried by
/// anyone via a block explorer's event log — not just someone who
/// already has a specific transaction hash.
///
/// This is the "extra credit" alternative to the raw self-transaction
/// approach in src/blockchain.py (which sends the hash directly in a
/// tx's data field, with no contract). Both approaches produce a
/// legitimate, tamper-evident, publicly verifiable on-chain record;
/// this version additionally supports discovery/enumeration.
contract FaceMatchRegistry {
    /// @dev Emitted every time a record hash is registered. `recordHash`
    /// is indexed so it can be looked up directly; `submitter` is
    /// indexed so all of one wallet's submissions can be filtered too.
    event RecordRegistered(
        bytes32 indexed recordHash,
        address indexed submitter,
        uint256 timestamp
    );

    /// @dev Tracks whether a given hash has already been registered, so
    /// re-submitting the exact same record is cheap to detect on-chain
    /// (and callers can decide whether that's an error or a no-op).
    mapping(bytes32 => bool) public isRegistered;

    /// @dev Maps a hash to the block timestamp it was first registered
    /// at, for simple on-chain lookups without needing to replay events.
    mapping(bytes32 => uint256) public registeredAt;

    /// @notice Register a face-match record hash on-chain.
    /// @param recordHash The SHA-256 hash of the canonical match record
    /// (see utils.record_hash() in the Python pipeline).
    function registerRecord(bytes32 recordHash) external {
        require(recordHash != bytes32(0), "recordHash cannot be zero");

        if (!isRegistered[recordHash]) {
            isRegistered[recordHash] = true;
            registeredAt[recordHash] = block.timestamp;
        }

        emit RecordRegistered(recordHash, msg.sender, block.timestamp);
    }

    /// @notice Convenience view: check whether a hash has ever been
    /// registered, and when.
    function checkRecord(bytes32 recordHash)
        external
        view
        returns (bool registered, uint256 timestamp)
    {
        return (isRegistered[recordHash], registeredAt[recordHash]);
    }
}
