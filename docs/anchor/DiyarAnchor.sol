// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

/// @title DIYAR daily-root anchor (reference contract; prototype deployment on the Sepolia testnet)
/// @notice Stores each day's signed SMT root in contract state, once, and keeps the head of DIYAR's daily
///         chain. Every new entry must cite the current head as its previous entry, and the contract
///         recomputes the entry itself with the same rule as diyar/ledger.py:
///             entry = SHA-256(0x20 || day || smtRoot || prev)
///         A second entry on the same previous head reverts, so the chain cannot be forked here:
///         Catena-style non-equivocation enforced by contract logic, not only made detectable.
///         Roots live in state, not only in event logs, so a past day can be checked with one call
///         even after a node has pruned old receipts.
contract DiyarAnchor {
    /// The only account allowed to write (phases 0 and 1 of the design have a single operator).
    address public immutable operator;
    /// Latest anchored entry; 32 zero bytes before the first anchor, which is also the ledger's genesis "prev".
    bytes32 public head;
    /// Number of days anchored so far.
    uint64 public count;
    /// Day of the latest entry, "YYYY-MM-DD" as 10 ASCII bytes; days must strictly increase.
    bytes10 public lastDay;
    /// Signed SMT root of every anchored day, written once; zero means the day was never anchored.
    mapping(bytes10 => bytes32) public rootOf;

    event Anchored(uint64 indexed index, bytes10 day, bytes32 smtRoot, bytes32 prev, bytes32 entry);

    error NotOperator();
    error WrongPrevious(bytes32 expected, bytes32 given);
    error DayNotIncreasing(bytes10 last, bytes10 given);
    error LengthMismatch();

    constructor() {
        operator = msg.sender;
    }

    /// The DIYAR ledger rule, exposed so anyone can recompute an entry from a published (day, root, prev).
    function entryHash(bytes10 day, bytes32 smtRoot, bytes32 prev) public pure returns (bytes32) {
        return sha256(abi.encodePacked(bytes1(0x20), day, smtRoot, prev));
    }

    /// Anchor one day. `prev` must equal the current head.
    function anchor(bytes10 day, bytes32 smtRoot, bytes32 prev) external returns (bytes32 entry) {
        if (msg.sender != operator) revert NotOperator();
        entry = _anchor(day, smtRoot, prev);
    }

    /// Anchor consecutive days in one transaction; each one extends the current head.
    function anchorBatch(bytes10[] calldata dayList, bytes32[] calldata roots) external returns (bytes32 entry) {
        if (msg.sender != operator) revert NotOperator();
        if (dayList.length != roots.length) revert LengthMismatch();
        for (uint256 i = 0; i < dayList.length; i++) {
            entry = _anchor(dayList[i], roots[i], head);
        }
    }

    function _anchor(bytes10 day, bytes32 smtRoot, bytes32 prev) internal returns (bytes32 entry) {
        if (prev != head) revert WrongPrevious(head, prev);
        if (count > 0 && day <= lastDay) revert DayNotIncreasing(lastDay, day);
        entry = entryHash(day, smtRoot, prev);
        emit Anchored(count, day, smtRoot, prev, entry);
        rootOf[day] = smtRoot;
        head = entry;
        lastDay = day;
        count += 1;
    }
}
