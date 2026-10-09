from langchain_core.prompts import ChatPromptTemplate


CORPUS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Write ordinary messages in a student startup team chat. Return structured data only. "
            "Write 12-16 realistic messages for one channel on one day, chronologically sorted. "
            "Use ISO 8601 created_at timestamps with the +05:30 offset on every message. "
            "Give every message a unique local_id in YYYYMMDD-NN form. Most messages should "
            "be top-level (parent_id null). Use 0-3 coherent threads per channel-day, each "
            "with 2-6 replies on one topic. Never create a one-reply thread: make both "
            "messages top-level or add a second relevant reply. Every reply's parent_id "
            "must name an earlier top-level root, never itself or another reply. "
            "Authors are persona ids. "
            "Use the supplied facts naturally. plants names facts newly introduced today on "
            "their first direct evidence messages. refs names facts from story_so_far, or "
            "facts introduced by an earlier message today, when a message mentions or "
            "restates their content, even if the wording changes. "
            "A fact's key_tokens in story_so_far always require its id in refs, and today's "
            "key_tokens require its id in plants. Both lists contain only F-number fact ids, "
            "never commands or other text. Today's fact ids belong in plants, never refs; "
            "earlier fact ids belong in refs, never plants. Do not put a today's fact id in "
            "refs before its first planted evidence message. Never put a fact id in message text. "
            "Paraphrase each fact "
            "in the author's voice. Preserve only exact error codes, commands, dates/times, "
            "and prescribed short replies verbatim. Treat story_so_far as dated history: "
            "follow the latest decision and never present an older reversed choice as current. "
            "Do not add future knowledge to earlier days. Filler must stay consistent with "
            "story_so_far and must not introduce new decisions, owners, deadlines, error "
            "codes, meeting times, or technology choices. Do not conflate distinct errors "
            "or their fixes. Do not write a new 'Decision:' recap in filler. People in the "
            "chat must sound unaware of any generation task: never mention personas, writing "
            "styles, language labels, consistency, these instructions, or a policy about "
            "decisions. Use Latin "
            "script for every author's words, including Hinglish. Include believable chatter: "
            "typos, lol, +1, off-topic notes, links, short replies and occasional code "
            "blocks. For every two Zoya messages, make at least one predominantly natural "
            "Latin-script Hinglish with Hindi sentence structure and several Hindi words, "
            "not merely one Hindi word in an English sentence. Meera uses checklists and "
            "acceptance criteria. Priya is short and "
            "decision-focused. A ref must state a prior fact's specific content, not merely "
            "share its topic. In particular, ref F01 only when the message states the demo "
            "date or the QR-check-in-plus-attendance-dashboard scope as information. Do not "
            "invent a decision or owner where the facts say none."
        ),
        ("human", "Channel-day brief (JSON):\n{brief}"),
    ]
)
