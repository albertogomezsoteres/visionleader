# Fast Downward Docker

Docker image that packages Fast Downward so the backend can call the classical
planner from Python without compiling it on the host. The image is built from a
pinned upstream release (`FD_RELEASE`, currently `release-24.06.1`) in a two-stage
build, so the runtime image only carries the planner binaries.

## Build the image

From the repository root:

```bash
make planner-image
# equivalent to: docker build -t fast-downward:latest docker/fast-downward
```

The build takes 5 to 10 minutes the first time and needs an internet connection (it
downloads the Fast Downward source). To try another release, pass
`--build-arg FD_RELEASE=<tag>`.

## Check the image

```bash
docker images | grep fast-downward
```

Expected output:

```
fast-downward   latest   <id>   <date>   <size>
```

## Run it directly (debug)

To run Fast Downward on a domain and problem pair:

```bash
docker run --rm -v "$(pwd)/pddl:/pddl" fast-downward:latest \
  domain.pddl problems/examples/problem_g_intra_example.pddl
```

The container mounts the repository's `pddl/` folder at `/pddl`. The output shows the
search and, if it succeeds, the plan line by line.

## Use from the backend

The backend never launches Docker by hand. `src/visionleader/navigation/fast_downward_client.py`
wraps the call and cleans up the temporary files. The planning endpoint (`/api/plan`)
needs the `fast-downward:latest` image available locally; if it is missing, the
response reports that no route could be computed.

## Troubleshooting

- `Cannot connect to the Docker daemon`: Docker Desktop is not running.
- `No such file or directory` inside the container: check that the `-v` mount points to a correct absolute path and that the PDDL file exists in that folder.
- Build fails: check disk space (about 2 GB during the build) and that the host has internet access.
