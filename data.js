/* data.js — everything on the site that changes, in one place. every page reads it.

   the easy way is _tools/ds (run `_tools/ds help`): it edits this file, checks it,
   commits and pushes. editing by hand works too, including on github.com from a
   phone: keep everything after the equals sign valid json (double quotes, no
   trailing commas), then run `_tools/ds check` when you're next at the laptop.

   start     day 001, mm.dd.yy, lagos
   pauses    [from, to] ranges when the clock was stopped; those days don't count
   days      one per working day, oldest first. d, date, msg, and optionally x (the
             post on x) and note (one extra sentence). a rest day is msg "rest"
   gates     newest first: title, page, cmd, status next|pass|fail, date (null = not run)
   writings  newest first: kind essay|note, title, page, date (null = still being written)
   garden    notes: id, label, status seed|growing|evergreen, planted, tended, page, scope
             links: [a, b] pairs. an edge is a claim */
window.DS={
"start":"08.31.26",
"pauses":[["09.21.26","11.02.26"]],
"days":[
{"d":1,"date":"08.31.26","msg":"gate minus 1: mmap loader + scalar dot product, 2.5002e+07","x":"https://x.com/elijahadeb/status/2094508977266532669?s=20"},
{"d":2,"date":"09.01.26","msg":"no number today. spent it on the mechanics —> simd, avx2, intel's intrinsics guide. worked out which handful of intrinsics a dot product actually needs. the guide lists thousands and explains none of them.","x":"https://x.com/elijahadeb/status/2094833631868977620?s=20"},
{"d":3,"date":"09.02.26","msg":"avx2 dot product working. 4.10x over scalar, 13.4 gb/s, passes the 1e-3 bar against a float64 reference. first run showed 33.8x —> ceiling is 8x, so i knew it was wrong. i was timing my disk against my ram. got it fixed, so the correct timing shows","x":"https://x.com/elijahadeb/status/2095220114333339918?s=20"},
{"d":4,"date":"09.03.26","msg":"implemented the threaded avx2 dot product and it returned exactly 0, so i spent most of this day debugging. std::async bound my args positionally to the wrong params —> every worker looped zero times, all twelve, no warning. fixed. now it runs but rel err is 3.157e-05 against 2.06e-09 single threaded, and my 1e-3 threshold called that a pass","x":"https://x.com/elijahadeb/status/2095552632798446070?s=20"},
{"d":5,"date":"09.04.26","msg":"fix precision loss in threaded avx2: block accumulators every 100k, fold into double. now, relative errors reads 2.06e-09 against 2.06e-09 single threaded, which are identical. added scalar tail loop","x":"https://x.com/elijahadeb/status/2095950364315156867?s=20"},
{"d":6,"date":"09.05.26","msg":"benchmarked all three paths properly. median of 9 runs, not one. 6.5 / 16.5 / 22.9 gb/s against a 38.4 absolute limit, so the threaded one pulls 60% of what the memory bus can theoretically do.","x":"https://x.com/elijahadeb/status/2096282595898143117?s=20"},
{"d":7,"date":"09.06.26","msg":"rest day"},
{"d":8,"date":"09.07.26","msg":"had the first pass on attention is all you need. understood that rnns were dropped due to lack of parallelism, they process a sequence one step at a time so you can't spread it across the hardware. additionally, started the gguf header parser, and generated a 35gb file to benchmark cold disk reads, since anything smaller than ram just sits in page cache and measures memory instead","x":"https://x.com/elijahadeb/status/2097009481607454779?s=20"},
{"d":9,"date":"09.08.26","msg":"mmap cold sequential read 0.4946 gb/s, median of 5, dd agrees within 0.3% difference. drive is m.2 sata not nvme, 4.5x under plan, started the 2nd pass on attention is all you need","x":"https://x.com/elijahadeb/status/2097371116318629928?s=20","note":"fact 2 repriced from 2–2.5 GB/s to 0.4946, so 70B Q4_K_M is ~86 s/token instead of ~20"},
{"d":10,"date":"09.09.26","msg":"gguf header parser started, not verified yet (can only be achieved when i'm done with the full gguf parser). attention paper pass 2 (started). day went to strategy","x":"https://x.com/elijahadeb/status/2097749004348227997?s=20"},
{"d":11,"date":"09.10.26","msg":"rest"},
{"d":12,"date":"09.11.26","msg":"gguf header parser written, spanning —> magic, version, tensor_count, metadata_kv_count. though still unverified against llama-gguf","x":"https://x.com/elijahadeb/status/2098470753746174452?s=20"},
{"d":13,"date":"09.12.26","msg":"gguf header verified against llama-gguf —> version 3, 23 kv pairs, 201 tensors. four exact matches. rest of day on c++","x":"https://x.com/elijahadeb/status/2098847395253752260?s=20"},
{"d":14,"date":"09.13.26","msg":"no code. week graded","x":"https://x.com/elijahadeb/status/2098847395253752260?s=20"},
{"d":15,"date":"09.14.26","msg":"gguf metadata table parsed, all 23 kv entries walked. read_string —> u64 length prefix, no null terminator","x":"https://x.com/elijahadeb/status/2099605845738680753?s=20"},
{"d":16,"date":"09.15.26","msg":"no new stage shipped. just re examined the metadata parser whilst figuring out why half those lines are even there. also spent time deepening my technical toolkit in c++","x":"https://x.com/elijahadeb/status/2100120197994615256?s=20"},
{"d":17,"date":"09.16.26","msg":"tensor info table parsed. 201 entries—name, n_dims, dims, ggml type, offset. computing per-tensor byte totals using a block table keyed on type id. q4_K is 256/144, q6_K is 256/210, f32 is 1/4. derived those constants straight from llama-gguf output instead of trusting a doc. slapped a 50 MiB length bound on every string before it gets used. alignment reads from metadata, defaults to 32. unverified against llama-gguf.","x":"https://x.com/elijahadeb/status/2100678624420708387?s=20"},
{"d":18,"date":"09.17.26","msg":"rest"},
{"d":19,"date":"09.18.26","msg":"did not ship. wrote out the full mental model of the gguf parser. cursor invariant, u64 length prefixes, logical elements vs physical bytes, block-based quantization, container layout and cache locality. also learnt a lot about the difference between std::map and std::flat_map both give you ordered keys. both give you log N lookup. same big-O. but wildly works differently.","x":"https://x.com/elijahadeb/status/2101351807041540269?s=20"},
{"d":20,"date":"09.19.26","msg":"no code. grounded c++ foundations. tracked raw byte movement into memory, object vs address vs byte-level lens. reinterpret_cast hands read() a physical destination without mutating the base uint32_t. array decay on char[4]. quantization reality check: q4_K 256 logical elements do not equal 144 physical bytes. stopping syntax memorization to build a rebuildable mental model","x":"https://x.com/elijahadeb/status/2101796387201380706?s=20"},
{"d":21,"date":"09.20.26","msg":"rest"}
],
"gates":[
{"title":"gate −1: three dot products and a number","page":"gate-minus-1.html","cmd":"$ make gate-minus-1 && ./gate-minus-1 a.f32 b.f32","status":"next","date":null}
],
"writings":[
{"kind":"essay","title":"why the slowest gpu i own is the whole point","page":"essay.html","date":"08.28.26"},
{"kind":"note","title":"the sum stops growing","page":"note-sum-stops-growing.html","date":null}
],
"garden":{
"notes":[
{"id":"mmap","label":"mmap & the page cache","status":"seed","planted":null,"tended":null,"page":null,"scope":"how a multi-gb weight file streams through 8 gb of ram — page faults, readahead, madvise, and what the kernel is actually doing under the engine."},
{"id":"gguf","label":"gguf, byte by byte","status":"seed","planted":null,"tended":null,"page":null,"scope":"the weight-file format read with a hex editor: header, metadata, tensor offsets, alignment — the map the engine walks at load time."},
{"id":"avx2","label":"avx2 intrinsics","status":"seed","planted":null,"tended":null,"page":null,"scope":"the 8-wide float kernels the engine lives on — fma, aligned loads, horizontal sums, and where the cycles actually go."},
{"id":"perf","label":"perf(1) & rapl","status":"seed","planted":null,"tended":null,"page":null,"scope":"reading the truth from the machine: cycles, cache misses, joules from the wall — the instruments behind every published number."},
{"id":"quant","label":"4-bit quantization","status":"seed","planted":null,"tended":null,"page":null,"scope":"packing weights into 4 bits without lobotomizing the model — block scales, dequant kernels, and the accuracy bill."},
{"id":"spec","label":"speculative decoding","status":"seed","planted":null,"tended":null,"page":null,"scope":"a small model drafts, the big one verifies — the accept-rate arithmetic that moves tokens-per-joule."}
],
"links":[["mmap","gguf"],["gguf","quant"],["quant","spec"],["avx2","quant"],["avx2","perf"],["perf","spec"],["mmap","perf"]]
}
};
