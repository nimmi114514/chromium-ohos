void ChromeDownloadManagerDelegate::CheckIsInstallationPackage(
    const std::string& file_name_,
    const std::string& file_size_,
    std::function<void(bool)> confirm_callback) {
  LOG(INFO) << "CheckIsInstallationPackage in";
  // The callback needs to be executed in the UI thread.
  scoped_refptr<base::SingleThreadTaskRunner> target_task_runner =
      base::SingleThreadTaskRunner::GetCurrentDefault();
  std::function<void(bool)> callback =
      [confirm_callback, target_task_runner](bool continue_download) {
        target_task_runner->PostTask(
            FROM_HERE, base::BindOnce(
                           [](std::function<void(bool)> func,
                              bool continue_download) {
                               func(continue_download);
                           },
                           confirm_callback, continue_download));
      };
  FileSelectPicker::GetInstance().ShowInstallationPackageDialog(
      file_name_, file_size_, callback);
}
