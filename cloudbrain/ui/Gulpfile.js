var gulp = require('gulp');
var browserSync = require('browser-sync').create();
var reload = browserSync.reload;

var pkg = require('./package.json');

/** Run local server to host ui folder
*/
gulp.task('serve:ui', function() {
  browserSync.init({
    port:3000,
    server: {
      baseDir: './'
    }
  });
  //Watch and Livereload html and js files in all folders
  gulp.watch(['./**/*.html', './**/*.js'], reload);
});

gulp.task('default', ['serve:ui']);