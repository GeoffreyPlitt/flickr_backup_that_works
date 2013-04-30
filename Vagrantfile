Vagrant.configure("2") do |config|
  config.vm.box = "precise32"
  config.vm.box_url = "http://files.vagrantup.com/precise32.box"
  config.vm.provision :shell, :inline => $BOOTSTRAP_SCRIPT # see below
end

$BOOTSTRAP_SCRIPT = <<EOF
	set -e # Stop on any error

	# --------------- SETTINGS ----------------
	# Other settings
	export DEBIAN_FRONTEND=noninteractive

	# --------------- APT-GET REPOS ----------------
	# Install prereqs
	sudo apt-get update
	sudo apt-get install -y python-software-properties memcached
	sudo apt-get update
	sudo apt-get install -y python-dev python-pip
	sudo pip install -U 'distribute>=0.6.28' # allows python to install things we need.
	cd /vagrant && sudo pip install -r requirements.txt
EOF
