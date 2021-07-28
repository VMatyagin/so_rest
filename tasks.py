from invoke import Context, task


@task
def setenv(c):
    ctx: Context = c
    ctx.run("while read v; do export $v ; done < .env")
