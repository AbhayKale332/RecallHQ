# Azure for Students — Free Services

Snapshot of the free monthly allowances on the Recova Azure for Students subscription, taken from the portal on 2026-10-11. All were at 0% usage at the time of the snapshot.

## What the Recova deployment uses

Deployment: VM `recova-vm` in resource group `recova-rg`, region `indiasouthcentral`, served at https://recova.indiasouthcentral.cloudapp.azure.com.

| Resource | Our config | Free allowance | Covered? | List price if not covered |
|---|---|---|---|---|
| Virtual machine | Standard_B2ats_v2 (Linux) | Basv2 Series, B2ats v2 — 750 h/month | Yes (24/7 ≈ 730 h) | ~$0.00615/h ≈ $4.50/month |
| OS disk | Premium SSD P6, 64 GB (switched from Standard SSD E4 on 2026-10-11) | Premium Page Blob P6 Disks — 2.2 disks/month | Yes | $10.21/month |
| Public IP | Standard IPv4 static | Public IP Addresses — 1,500 h/month | Yes | $0.005/h ≈ $3.65/month |
| Outbound traffic | Demo traffic | Data Transfer Out — 15 GB/month | Yes, while under 15 GB | Per-GB beyond 15 GB |

**Expected cost:** about $0/month while usage stays within the allowances above.

Usage in the portal lags by roughly 24–48 hours, so a running resource can still show "Not in use".

## Full list of free allowances (per month)

### Compute

| Service | Allowance |
|---|---|
| Virtual Machines, BS Series, B1s (Linux) | 750 hours |
| Virtual Machines, BS Series Windows, B1s | 750 hours |
| Virtual Machines, Basv2 Series, B2ats v2 (Linux, x64) | 750 hours |
| Virtual Machines, Basv2 Series Windows, B2ats v2 | 750 hours |
| Virtual Machines, Bpsv2 Series, B2pts v2 (Linux, Arm64) | 750 hours |
| Virtual Machines, Bpsv2 Series Windows, B2pts v2 | 750 hours |
| Virtual Machines Licenses, Red Hat Enterprise Linux, 1 vCPU VM License | 750 hours |

### Storage

| Service | Allowance |
|---|---|
| Premium Page Blob, P6 Disks (64 GB Premium SSD) | 2.2 disks |
| Standard HDD Managed Disks, LRS Snapshots | 1 GB |
| Standard HDD Managed Disks, Disk Operations | 2M (200 × 10K) |
| Files, LRS Data Stored | 100 GB |
| Files, Read Operations | 40K |
| Files, LRS Write Operations | 10K |
| Files, Protocol Operations | 40K |
| Files, List Operations | 10K |
| Tiered Block Blob, Hot LRS Data Stored | 5 GB |
| Tiered Block Blob, Hot Read Operations | 20K |
| Tiered Block Blob, Hot LRS Write Operations | 10K |
| Tiered Block Blob, LRS List and Create Container Operations | 20K |
| Tiered Block Blob, Archive LRS Data Stored | 10 GB |
| Tiered Block Blob, Archive Data Retrieval | 10 GB |
| Tiered Block Blob, Archive Read Operations | 100 |

### Databases

| Service | Allowance |
|---|---|
| Azure Database for PostgreSQL, Flexible Server, Burstable B1MS compute | 750 hours |
| Azure Database for PostgreSQL, Flexible Server Storage | 32 GB |
| Azure Database for PostgreSQL, Flexible Server Backup Storage (LRS) | 32 GB |
| Azure Database for MySQL, Flexible Server, Burstable B1MS compute | 750 hours |
| Azure Database for MySQL, Flexible Server Storage | 32 GB |
| Azure Database for MySQL, Flexible Server Backup Storage (LRS) | 32 GB |
| SQL Database, Single Standard, S0 DTUs | 31 days |
| Azure Cosmos DB, Free Data Stored | 25 GB |
| Azure Cosmos DB, Free 100 RU/s | 2,976 hours |

### Networking

| Service | Allowance |
|---|---|
| Public IP Addresses, IP Address Hours | 1,500 hours |
| Data Transfer Out | 15 GB |
| Load Balancer, Standard, Included LB Rules and Outbound Rules | 750 hours |
| Load Balancer, Standard, Overage LB Rules and Outbound Rules | 5 hours |
| Load Balancer, Standard, Data Processed | 15 GB |
| VPN Gateway, Gateway | 750 hours |

### Containers, messaging, security

| Service | Allowance |
|---|---|
| Container Registry, Standard Registry Unit | 31 days |
| Service Bus, Standard Base Unit | 750 hours |
| Key Vault, Premium HSM | 10,000 operations |

### AI / Cognitive Services

| Service | Allowance |
|---|---|
| Custom Vision, S0 Transactions | 10K |
| Custom Vision, S0 Training | 1 hour |
| Custom Vision, S0 Image Storage | 10K |
| Computer Vision, S1 Transactions | 5K |
| Language Understanding, Speech to Intent | 10K |
| QnA Maker, Standard Unit | 3 days |
| Face, Standard Transactions | 30K |
| Translator Text, S1 Translation Transactions | 2M characters |
| Text Analytics, Standard Text Records | 5K |
| Content Moderator, Standard Transactions | 10K |
| Anomaly Detector, Standard Transactions | 20K |
| Ink Recognizer, S0 Transactions | 2K |
| Personalizer, S0 Transactions | 50K |
| Azure Form Recognizer (Applied AI), S0 Transactions | 500 |

### Media Services

| Service | Allowance |
|---|---|
| Video On Demand Encoding, Standard Output Content Minute | 20 minutes |
| Streaming Units, Standard Unit | 0.01 units |
| Live Channels, Transcription Event | 5 hours |
| Live Channels, Pass | 5 hours |

## Possible later upgrade

The free PostgreSQL Flexible Server (B1MS, 32 GB) could replace the on-VM SQLite file. Point the backend's `DATABASE_URL` at it to get managed backups and keep data independent of the VM.
