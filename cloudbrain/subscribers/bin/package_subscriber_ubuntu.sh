pyinstaller --onefile -y --clean ../file_writer_subscriber.py
rm -rf build
rm file_writer_subscriber.spec
rm -rf ubuntu
mv dist ubuntu
