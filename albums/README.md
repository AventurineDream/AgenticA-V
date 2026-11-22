# Albums

One folder per band, `B-NN-<band slug>/`, holding one folder per album, `A-NN-<album slug>/`, with
`album.md` and a `tracks/` folder of track docs named `NN-<track slug>.md`. The formats are in the
[band and album spec](../docs/spec/band-album-spec.md) and the [templates](../templates/);
`uv run python -m agentic_av.registry` checks them.

The A-01 and A-02 albums predate the spec. Their record is the bundled players and the discography
rows in each band doc, so they have no album docs here. Album docs land here from round 3 (A-03) on,
made with [the swarm prompt](../prompts/swarm.md) or by hand. Test-scope albums, such as the
[worked test](../docs/spec/worked-test/README.md), stay out of this folder.
