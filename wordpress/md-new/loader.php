<?php
/**
 * Load Gatilab child-theme customizations from this file.
 *
 * @package MD_New
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$blog_rankings = MD_CHILD_DIR . 'inc/blog-rankings.php';
if ( file_exists( $blog_rankings ) ) {
	require_once $blog_rankings;
}

$footer_customization = MD_CHILD_DIR . 'inc/footer.php';
if ( file_exists( $footer_customization ) ) {
	require_once $footer_customization;
}
