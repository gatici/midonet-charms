import subprocess

def pre_install():
    """
    Do any setup required before the install hook.
    """
    install_charmhelpers()
    cmd_apt = "sudo apt-get update --fix-missing"
    subprocess.check_output(cmd_apt, shell=True)
    cmd_puppet = "sudo apt-get install -y puppet"
    subprocess.check_output(cmd_puppet, shell=True)


def install_charmhelpers():
    """
    Install the charmhelpers library, if not present.
    """
    try:
        import charmhelpers  # noqa
    except ImportError:
        import subprocess
        #subprocess.check_call(['apt-get', 'install', '-y', 'python-pip'])
        #subprocess.check_call(['pip', 'install', 'charmhelpers'])
