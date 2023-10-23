# Self contained docker image with VTK/OCCT/pythonocc/solvespace

You should only need two commands:

```
docker_build.sh
docker_run.sh # starts interactive session
```

It will take a very long time to build the image initially, as the above tools will be compiled
from source.

Note that the `docker_run.sh` attempts to connect to a container X11 socket. If you run into
problems with it and don't need UI, you can remove the entrypoint script.

# installing custom VTK wrapped modules

Check the VTK example for your module structure: `/third_party/VTK/Examples/Modules/Wrapping`

`mkdir build && cd build && cmake .. -DCMAKE_INSTALL_PREFIX=/root/.local`

Then the usual:

`make`

`make install`

Since shared libs are generated/installed, you also must run

`ldconfig`

after installing.

