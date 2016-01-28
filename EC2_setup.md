# EC2 Config

Open ports 4001, 5001, 8080


# Install Packages

* `sudo apt-get install -y git`


# Install Go-lang 1.5

https://golang.org/doc/install


* `wget https://storage.googleapis.com/golang/go1.5.3.linux-amd64.tar.gz`
* `sudo tar -C /usr/local -xzf go1.5.3.linux-amd64.tar.gz`

Setup go workspace

* `mkdir -p ~/go-workspace`

Add go to path

```shell
#~/.bash_profile

export PATH=$PATH:/usr/local/go/bin
export GOPATH=$HOME/go-workspace
```

# Mount data drive

* `sudo mkfs -t ext4 /dev/xvdb`
* `sudo mkdir -p /data`
* `sudo mount /dev/xvdb /data`
* `sudo mkdir -p /data/ipfs`
* `sudo mkdir -p /data/ipfs-repo`
* `sudo mkdir -p /data/ipns`
* `sudo chown ubunto /data/ipfs`
* `sudo chown ubunto /data/ipfs-repo`
* `sudo chown ubunto /data/ipns`


# Install IPFS

* `go get -u github.com/ipfs/go-ipfs/cmd/ipfs`

Add IPFS to $PATH


```shell
#~/.bash_profile

export IPFS_PATH=/data/ipfs-repo
export GOPATH=$HOME/go-workspace
export PATH=$GOPATH/bin:$PATH:/usr/local/go/bin
export PATH=$PATH:/usr/local/opt/go/libexec/bin
```

# Install IPFS-Update

* `go get -u github.com/ipfs/ipfs-update`

# Install Fuse

* `sudo apt-get install -y fuse`

Authorize the ubuntu user to be in the fuse group

* `sudo usermod -a -G fuse ubuntu`

Change Ownership to the ubuntu user

* `sudo chown ubuntu:fuse /etc/fuse.conf /dev/fuse`

# Install Supervisord

* `sudo apt-get install -y supervisor`

Configure IPFS

```
# /etc/supervisor/conf.d/ipfs.conf

command=/home/ubuntu/go-workspace/bin/ipfs daemon --init --mount-ipfs /data/ipfs --mount-ipns /data/ipns --mount
environment=IPFS_PATH="/data/ipfs-repo"
user=ubuntu
stdout_logfile=/var/log/supervisor/ipfs-stdout.log
stderr_logfile=/var/log/supervisor/ipfs-stderr.log
```

Reload supervisord

* `sudu supervisorctl reload`
* `sudu supervisorctl status`

Monitor IPFS with `tail`

```bash
$ tail -f /var/log/supervisor/ipfs*.log
```
