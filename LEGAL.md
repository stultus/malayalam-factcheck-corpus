# Legal

This is a non-commercial research project. The pipeline collects publicly available fact-check articles from Indian publishers and produces structured records intended for academic and non-commercial research into misinformation detection. This document explains the project's position. It is not legal advice.

## Source content and ownership

All source articles ingested by this pipeline remain the property of their original publishers. This project asserts no ownership over source content and does not relicense it. Where structured records derived from source articles are released, the release is made for non-commercial research use under fair dealing (Indian Copyright Act 1957, Section 52(1)(a)) and analogous research provisions in other jurisdictions. Original publishers retain all moral and economic rights in their work.

## How the pipeline operates

- `robots.txt` is respected for every host.
- All requests carry an identifiable `User-Agent` that names the project, states a research purpose, and provides a contact email.
- Per-host rate limits and concurrency caps are enforced (defaults: 3-second delay, two concurrent requests per host).
- Source attribution — publisher, author, URL, original publication date — is preserved on every record.
- Responses are cached so that re-runs do not re-load source servers.

## Personal data

Fact-check articles routinely name individuals alleged to have spread misinformation. This project does not augment, identify, link, or enrich records against named individuals, and does not release datasets intended to enable such use. Named individuals or their representatives who wish to have records removed should follow [TAKEDOWN.md](TAKEDOWN.md). This posture is informed by India's Digital Personal Data Protection Act 2023.

## Code license vs. corpus license

[LICENSE](LICENSE) (MIT) covers the **pipeline code only**. Any released corpus is a separate work from the code. Released corpora ship with their own license file and are made available for non-commercial research use only. The MIT license on the code does not extend to article text, claims, verdicts, or any other content collected from source publishers.

## No verdict on the underlying claims

This project does not endorse, contest, or independently verify the fact-check verdicts produced by source publishers. Records reflect what the publisher said about a claim, not the maintainers' own assessment of either the claim or the publisher.

## No warranty

The pipeline and any released corpus are provided "as is" without warranty of any kind, express or implied, including but not limited to warranties of accuracy, completeness, non-infringement, or fitness for a particular purpose. Users of the code or any released corpus are responsible for their own compliance with applicable law in their jurisdiction.

## Takedown

See [TAKEDOWN.md](TAKEDOWN.md).

## Contact

hello@stultus.in
