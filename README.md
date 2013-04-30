flickr_backup_that_works
========================

Flickr backup script that actually works, with RESUME. Downloads the originals, from your entire Flickr account.

It saves ALL of your photos like this:
./DOWNLOADED/SET_NAME/PHOTO_NAME_PLUS_DUPLICATE_SUFFIX.EXT

Notes:
- Photos in the same set with the same name have an incrementing suffix added so they can be downloaded without clobbering each other.
- Photos with no set are saved in a folder called "__NO_SET__"
- It could take many hours to finish, so I made it resumable. Results are cached in memcache, so it will quickly fly through already downloaded ones.
- To run it, install Vagrant, do "vagrant up" and "vagrant ssh",  and then "python download_all_with_resume.py".
