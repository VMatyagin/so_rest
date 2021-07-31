from invoke import Context, task


@task
def setenv(c):
    ctx: Context = c
    with open(".env") as f:
        for var in f.readlines():
            ctx.run(f"export {var}")


@task
def db(c):
    ctx: Context = c
    ctx.run("docker compose up db")
