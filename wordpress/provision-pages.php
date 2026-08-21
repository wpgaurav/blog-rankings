<?php
/**
 * Provision draft Gatilab Blog Rankings pages through WP-CLI eval-file.
 *
 * @package Gatilab_Blog_Rankings
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$hub = get_page_by_path( 'blog-rankings', OBJECT, 'page' );
if ( ! $hub || 'publish' !== $hub->post_status ) {
	throw new RuntimeException( 'Published blog-rankings hub not found.' );
}

$ranking_preview = get_page_by_path( 'blog-rankings-preview', OBJECT, 'page' );
if ( $ranking_preview && 'publish' === $ranking_preview->post_status ) {
	throw new RuntimeException( 'Refusing to modify a published blog-rankings-preview page.' );
}

$preview_id = $ranking_preview ? $ranking_preview->ID : wp_insert_post(
	array(
		'post_type'    => 'page',
		'post_status'  => 'draft',
		'post_title'   => 'Gatilab Blog Rankings Preview',
		'post_name'    => 'blog-rankings-preview',
		'post_content' => '',
	),
	true
);

if ( is_wp_error( $preview_id ) ) {
	throw new RuntimeException( esc_html( $preview_id->get_error_message() ) );
}

update_post_meta( $preview_id, '_wp_page_template', 'templates/blog-rankings-hub.php' );

$categories = array(
	'technology'            => 'Technology Blog Rankings',
	'business'              => 'Business and Entrepreneurship Blog Rankings',
	'marketing-seo'         => 'Marketing and SEO Blog Rankings',
	'personal-finance'      => 'Personal Finance Blog Rankings',
	'science'               => 'Science Blog Rankings',
	'education'             => 'Education Blog Rankings',
	'health'                => 'Health and Wellness Blog Rankings',
	'travel'                => 'Travel Blog Rankings',
	'food'                  => 'Food Blog Rankings',
	'culture-entertainment' => 'Culture and Entertainment Blog Rankings',
);

$created = array();
foreach ( $categories as $slug => $category_title ) {
	$ranking_page = get_page_by_path( 'blog-rankings/' . $slug, OBJECT, 'page' );
	if ( $ranking_page && 'publish' === $ranking_page->post_status ) {
		throw new RuntimeException( sprintf( 'Refusing to modify published page %s.', sanitize_key( $slug ) ) );
	}

	$page_id = $ranking_page ? $ranking_page->ID : wp_insert_post(
		array(
			'post_type'    => 'page',
			'post_status'  => 'draft',
			'post_parent'  => $hub->ID,
			'post_title'   => $category_title,
			'post_name'    => $slug,
			'post_content' => '',
		),
		true
	);

	if ( is_wp_error( $page_id ) ) {
		throw new RuntimeException( esc_html( $page_id->get_error_message() ) );
	}

	update_post_meta( $page_id, '_wp_page_template', 'templates/blog-ranking-category.php' );
	update_post_meta( $page_id, '_gatilab_br_category', $slug );
	$created[] = array(
		'id'       => $page_id,
		'slug'     => $slug,
		'status'   => get_post_status( $page_id ),
		'template' => get_page_template_slug( $page_id ),
		'preview'  => get_preview_post_link( $page_id ),
	);
}

flush_rewrite_rules( false );

echo wp_json_encode(
	array(
		'hub_id'           => $hub->ID,
		'hub_status'       => $hub->post_status,
		'preview_hub_id'   => $preview_id,
		'preview_template' => get_page_template_slug( $preview_id ),
		'category_pages'   => $created,
	),
	JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES
);
