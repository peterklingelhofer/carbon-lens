"""Ethereum wallet scaffolding — key management, transaction building, bounty claiming.

Handles the on-chain side of the ZK proof broker:
  1. Manage prover wallet (private key from env, keystore, or hardware wallet)
  2. Submit proof transactions to prover network smart contracts
  3. Claim bounties after successful proof verification
  4. Track gas costs and net earnings

This module builds and signs transactions without broadcasting —
the actual broadcast is deferred until the wallet is funded and
accounts are created on the target networks.

Supports: Ethereum L1, Scroll, zkSync, StarkNet, Aleo (via adapters).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from carbon_mesh.models.zk import (
    ProverNetwork,
    TransactionReceipt,
    WalletInfo,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class WalletBackend(Protocol):
    """Protocol for blockchain wallet operations."""

    async def get_info(self) -> WalletInfo: ...
    async def submit_proof(self, network: ProverNetwork, job_id: str, proof_data: bytes) -> TransactionReceipt: ...
    async def claim_bounty(self, network: ProverNetwork, job_id: str, tx_hash: str) -> TransactionReceipt: ...
    async def estimate_gas(self, network: ProverNetwork, data_size_bytes: int) -> float: ...


class LocalWallet:
    """Local Ethereum wallet using private key from environment.

    For development and testing. In production, use a hardware wallet
    or KMS-backed signer.

    Does NOT broadcast transactions — builds and signs them locally,
    returns the signed tx hash for inspection.
    """

    def __init__(self, private_key: str = "", chain_id: int = 1) -> None:
        self._private_key = private_key
        self._chain_id = chain_id
        self._address = self._derive_address(private_key) if private_key else ""
        self._nonce = 0
        self._tx_log: list[TransactionReceipt] = []

    async def get_info(self) -> WalletInfo:
        return WalletInfo(
            address=self._address or "0x" + "0" * 40,
            chain_id=self._chain_id,
            balance_eth=0.0,  # Would query RPC
            balance_usdc=0.0,
            nonce=self._nonce,
        )

    async def submit_proof(
        self, network: ProverNetwork, job_id: str, proof_data: bytes,
    ) -> TransactionReceipt:
        """Build a proof submission transaction.

        Different networks have different submission contracts:
        - Boundless: ProofMarketplace.submitProof(bytes32 jobId, bytes proof)
        - Succinct: SP1Verifier.verify(bytes proof, bytes publicValues)
        - Scroll: ScrollChain.finalizeBatchWithProof(...)
        - Aleo: Direct to network via RPC

        This builds the calldata but does NOT broadcast.
        """
        contract = NETWORK_CONTRACTS.get(network)
        if not contract:
            logger.warning("No contract configured for network %s", network.value)

        # Build transaction calldata
        # In production: encode ABI, estimate gas, set nonce, sign
        tx_data = self._build_submit_calldata(network, job_id, proof_data)
        tx_hash = "0x" + hashlib.sha256(tx_data).hexdigest()

        receipt = TransactionReceipt(
            tx_hash=tx_hash,
            status="built",  # Not broadcast yet
            gas_used=0,
            gas_price_gwei=0.0,
            cost_eth=0.0,
        )

        self._tx_log.append(receipt)
        self._nonce += 1

        logger.info(
            "Built proof submission tx for %s job %s: %s (not broadcast)",
            network.value, job_id, tx_hash,
        )
        return receipt

    async def claim_bounty(
        self, network: ProverNetwork, job_id: str, tx_hash: str,
    ) -> TransactionReceipt:
        """Build a bounty claim transaction.

        Called after the proof has been verified on-chain.
        The bounty is released from the escrow contract to our wallet.
        """
        claim_data = self._build_claim_calldata(network, job_id, tx_hash)
        claim_hash = "0x" + hashlib.sha256(claim_data).hexdigest()

        receipt = TransactionReceipt(
            tx_hash=claim_hash,
            status="built",
            gas_used=0,
            gas_price_gwei=0.0,
            cost_eth=0.0,
        )

        self._tx_log.append(receipt)
        logger.info(
            "Built bounty claim tx for %s job %s: %s (not broadcast)",
            network.value, job_id, claim_hash,
        )
        return receipt

    async def estimate_gas(self, network: ProverNetwork, data_size_bytes: int) -> float:
        """Estimate gas cost in USD for a proof submission.

        Uses typical gas prices and proof calldata sizes.
        """
        estimates = GAS_ESTIMATES.get(network, GAS_ESTIMATES[ProverNetwork.BOUNDLESS])
        # Base gas + calldata gas (16 gas per non-zero byte)
        gas_units = estimates["base_gas"] + data_size_bytes * 16
        # Assume 30 gwei gas price, ETH at ~$2500
        gas_price_gwei = 30.0
        gas_cost_eth = gas_units * gas_price_gwei * 1e-9
        gas_cost_usd = gas_cost_eth * 2500.0
        return round(gas_cost_usd, 4)

    def get_transaction_log(self) -> list[TransactionReceipt]:
        """Get all transactions built by this wallet."""
        return list(self._tx_log)

    @staticmethod
    def _derive_address(private_key: str) -> str:
        """Derive Ethereum address from private key.

        In production, use eth_account.Account.from_key().
        This is a placeholder that returns a deterministic address.
        """
        if not private_key:
            return ""
        # Deterministic placeholder — real implementation uses secp256k1
        h = hashlib.sha256(private_key.encode()).hexdigest()
        return "0x" + h[:40]

    @staticmethod
    def _build_submit_calldata(network: ProverNetwork, job_id: str, proof_data: bytes) -> bytes:
        """Build ABI-encoded calldata for proof submission.

        In production, use eth_abi.encode or web3.py contract.functions.
        """
        # Function selector: submitProof(bytes32,bytes)
        selector = b"\x12\x34\x56\x78"  # Placeholder
        job_bytes = job_id.encode().ljust(32, b"\x00")[:32]
        return selector + job_bytes + proof_data[:256]

    @staticmethod
    def _build_claim_calldata(network: ProverNetwork, job_id: str, tx_hash: str) -> bytes:
        """Build ABI-encoded calldata for bounty claim."""
        selector = b"\xab\xcd\xef\x01"  # Placeholder
        job_bytes = job_id.encode().ljust(32, b"\x00")[:32]
        hex_str = tx_hash[2:] if tx_hash.startswith("0x") else tx_hash
        # Pad to even length for fromhex
        if len(hex_str) % 2:
            hex_str = "0" + hex_str
        try:
            tx_bytes = bytes.fromhex(hex_str)
        except ValueError:
            tx_bytes = tx_hash.encode()
        return selector + job_bytes + tx_bytes[:32]


# --- Network contract addresses (mainnet) ---

NETWORK_CONTRACTS: dict[ProverNetwork, dict] = {
    ProverNetwork.BOUNDLESS: {
        "chain": "ethereum",
        "chain_id": 1,
        "contract": "",  # To be filled when account is created
        "name": "Boundless ProofMarketplace",
    },
    ProverNetwork.SUCCINCT: {
        "chain": "ethereum",
        "chain_id": 1,
        "contract": "",
        "name": "Succinct SP1 Verifier Gateway",
    },
    ProverNetwork.SCROLL: {
        "chain": "ethereum",
        "chain_id": 1,
        "contract": "",
        "name": "Scroll L1 Rollup Contract",
    },
    ProverNetwork.ZKSYNC: {
        "chain": "ethereum",
        "chain_id": 1,
        "contract": "",
        "name": "zkSync Diamond Proxy",
    },
    ProverNetwork.STARKNET: {
        "chain": "ethereum",
        "chain_id": 1,
        "contract": "",
        "name": "StarkNet Core Contract",
    },
    ProverNetwork.ALEO: {
        "chain": "aleo",
        "chain_id": 0,
        "contract": "",
        "name": "Aleo Prover Rewards",
    },
    ProverNetwork.GEVULOT: {
        "chain": "ethereum",
        "chain_id": 1,
        "contract": "",
        "name": "Gevulot Prover Registry",
    },
    ProverNetwork.TAIKO: {
        "chain": "ethereum",
        "chain_id": 1,
        "contract": "",
        "name": "Taiko L1 Contract",
    },
}

# --- Gas estimates per network ---

GAS_ESTIMATES: dict[ProverNetwork, dict] = {
    ProverNetwork.BOUNDLESS: {"base_gas": 150_000, "typical_proof_bytes": 256},
    ProverNetwork.SUCCINCT: {"base_gas": 200_000, "typical_proof_bytes": 384},
    ProverNetwork.SCROLL: {"base_gas": 300_000, "typical_proof_bytes": 1024},
    ProverNetwork.ALEO: {"base_gas": 100_000, "typical_proof_bytes": 192},
    ProverNetwork.GEVULOT: {"base_gas": 180_000, "typical_proof_bytes": 512},
    ProverNetwork.ZKSYNC: {"base_gas": 250_000, "typical_proof_bytes": 768},
    ProverNetwork.STARKNET: {"base_gas": 350_000, "typical_proof_bytes": 2048},
    ProverNetwork.TAIKO: {"base_gas": 200_000, "typical_proof_bytes": 384},
}
