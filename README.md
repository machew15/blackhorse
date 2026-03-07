# Blackhorse Mesh

> Offline-first, cryptographically governed mesh networking for communities without reliable connectivity.

---

## What This Is

Blackhorse Mesh is a communication layer built for people in places where the internet
is unreliable, expensive, or absent. It allows devices to exchange messages securely
with one another directly — without a server, without a cloud provider, and without
asking anyone's permission. Every message is encrypted and signed before it ever
leaves the device. The principle behind it is ubuntu: the network only works because
its participants make it work together.

---

## How It Works

- **Offline-first.** Messages are composed, encrypted, and queued locally. When a relay
  node comes within range, the queue flushes automatically and delivers in order.

- **Spatial layer.** Nodes maintain awareness of their physical and logical proximity
  to other nodes. The mesh routes toward known good paths without any central index.

- **Governance layer.** Trust is earned through contribution. Nodes that relay messages
  reliably accumulate trust. Policy decisions — such as relay limits and quorum thresholds
  — are set by the community of participating nodes, not by any single authority.

---

## What This Does NOT Do

- No blockchain. No token. No coin.
- No central authority or registration server.
- No persistent identity that can be subpoenaed or seized.
- No analytics, telemetry, or data collection of any kind.

---

## Status

Early development. Not production ready. APIs and wire formats may change without notice.

---

## License

MIT — open by design, sovereign by intent.
