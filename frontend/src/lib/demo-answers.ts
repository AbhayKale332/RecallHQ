// Prepared from the synthetic archive; only an exact, unchanged command uses these answers.
export const DEMO_COMMANDS = {
  "eng": {
    "input": "/ask Why did the team switch from MongoDB to Postgres for the pilot?",
    "result": {
      "kind": "answer",
      "answer": "The team switched to Postgres because reporting and export joins were getting messy with MongoDB. Postgres also made check-in deduplication cleaner through database constraints. The change was limited to the data layer, and the October 2 pilot stayed on schedule.",
      "sources": [
        {
          "id": "synthetic:eng:20260915-01",
          "channel": "eng",
          "author": "priya",
          "author_name": "Priya Shah",
          "text": "Quick update: we're staying on Postgres, not Mongo, for the pilot data model. Reporting joins and dedupe rules are cleaner that way. Can someone own the migration check today?",
          "created_at": "2026-09-15T09:12:00+05:30",
          "thread_root_id": null
        },
        {
          "id": "synthetic:eng:20260914-06",
          "channel": "eng",
          "author": "priya",
          "author_name": "Priya Shah",
          "text": "Decision: Postgres replaces MongoDB for the prototype. The switch stays limited to the data layer, and the 2026-10-02 pilot remains on schedule.",
          "created_at": "2026-09-14T09:31:00+05:30",
          "thread_root_id": "synthetic:eng:20260914-02"
        }
      ]
    }
  },
  "product": {
    "input": "/ask What is included in the pilot, and how will success be measured?",
    "result": {
      "kind": "answer",
      "answer": "The October 2 campus pilot includes QR check-in and an attendance dashboard. The success target is at least 95% successful check-ins for 100 attendees, measured from exported attendance rows.",
      "sources": [
        {
          "id": "synthetic:product:20260826-01",
          "channel": "product",
          "author": "meera",
          "author_name": "Meera Iyer",
          "text": "Quick scope check for today:\n- Demo target stays 2026-10-02\n- First release stays QR check-in + attendance dashboard\n- Success bar: 95% successful check-ins for 100 attendees, measured from exported attendance rows\nIf anyone wants to narrow or expand, please say so before I turn this into a checklist.",
          "created_at": "2026-08-26T09:10:00+05:30",
          "thread_root_id": null
        }
      ]
    }
  },
  "ops": {
    "input": "/ask Where is the pilot being held, and who owns the venue booking?",
    "result": {
      "kind": "answer",
      "answer": "The October 2 pilot is booked in Seminar Hall B, which has capacity for 120 people. Zoya Khan owns the venue booking and confirmation. The booking was confirmed on September 4.",
      "sources": [
        {
          "id": "synthetic:ops:20260825-02",
          "channel": "ops",
          "author": "zoya",
          "author_name": "Zoya Khan",
          "text": "haan, i’ve got venue on my plate. main abhi admin desk se baat kar rahi hoon, Seminar Hall B ka availability check kara diya hai, and i’ll push for confirmation asap. agar kuch form ya approval chahiye hua toh i’ll flag it here.",
          "created_at": "2026-08-25T09:12:00+05:30",
          "thread_root_id": "synthetic:ops:20260825-01"
        },
        {
          "id": "synthetic:ops:20260904-01",
          "channel": "ops",
          "author": "zoya",
          "author_name": "Zoya Khan",
          "text": "update: Seminar Hall B is booked for the pilot on 2026-10-02, and it can take 120 people. 👍",
          "created_at": "2026-09-04T09:10:00+05:30",
          "thread_root_id": null
        }
      ]
    }
  },
  "build-help": {
    "input": "/ask How did the team fix the Postgres 28P01 authentication error?",
    "result": {
      "kind": "answer",
      "answer": "Nikhil traced the local Postgres 28P01 password authentication error to a stale demo volume. He reset that local demo volume with:\n\ndocker compose down -v && docker compose up -d\n\nPostgres then started cleanly. This was the stale-volume fix for the local demo setup.",
      "sources": [
        {
          "id": "synthetic:build-help:20260902-01",
          "channel": "build-help",
          "author": "nikhil",
          "author_name": "Nikhil Menon",
          "text": "local Postgres is tripping on 28P01 again. i had the stale demo volume on this box, so i reset it with `docker compose down -v && docker compose up -d` and it came back clean.",
          "created_at": "2026-09-02T09:05:00+05:30",
          "thread_root_id": null
        }
      ]
    }
  },
  "random": {
    "input": "/ask What is the team’s internal demo nickname, and what is the public product name?",
    "result": {
      "kind": "answer",
      "answer": "Firefly is the team’s internal demo nickname. Beacon remains the public product name used in external docs and screenshots.",
      "sources": [
        {
          "id": "synthetic:random:20260908-07",
          "channel": "random",
          "author": "priya",
          "author_name": "Priya Shah",
          "text": "Keeping this simple: Firefly is the internal demo nickname, Beacon is still the name we show outside. Please use that split in any docs or screenshots.",
          "created_at": "2026-09-08T11:05:00+05:30",
          "thread_root_id": null
        }
      ]
    }
  }
} as const;
