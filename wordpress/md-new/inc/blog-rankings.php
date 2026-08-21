<?php
/**
 * Gatilab Blog Rankings data, templates, REST API, cron, and administration.
 *
 * @package MD_New
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const GATILAB_BR_VERSION        = '0.1.0';
const GATILAB_BR_CRON_HOOK      = 'gatilab_br_refresh_rankings';
const GATILAB_BR_DEFAULT_SOURCE = 'https://raw.githubusercontent.com/wpgaurav/blog-rankings/main/dist/web/latest/';

/**
 * Return the 10 launch categories.
 *
 * @return array<string, array<string, string>>
 */
function gatilab_br_categories() {
	return array(
		'technology'            => array(
			'name'        => __( 'Technology', 'md-new' ),
			'description' => __( 'Software, devices, AI, security, and the systems shaping technology.', 'md-new' ),
		),
		'business'              => array(
			'name'        => __( 'Business and Entrepreneurship', 'md-new' ),
			'description' => __( 'Companies, startups, SaaS, leadership, operations, and creator businesses.', 'md-new' ),
		),
		'marketing-seo'         => array(
			'name'        => __( 'Marketing and SEO', 'md-new' ),
			'description' => __( 'Search, content, copywriting, distribution, analytics, and paid acquisition.', 'md-new' ),
		),
		'personal-finance'      => array(
			'name'        => __( 'Personal Finance', 'md-new' ),
			'description' => __( 'Saving, investing, debt, tax, planning, and financial independence.', 'md-new' ),
		),
		'science'               => array(
			'name'        => __( 'Science', 'md-new' ),
			'description' => __( 'Research communication across the physical, life, earth, space, and environmental sciences.', 'md-new' ),
		),
		'education'             => array(
			'name'        => __( 'Education', 'md-new' ),
			'description' => __( 'Teaching, learning science, higher education, curriculum, and study practice.', 'md-new' ),
		),
		'health'                => array(
			'name'        => __( 'Health and Wellness', 'md-new' ),
			'description' => __( 'Public health, fitness, nutrition, mental health, and sustainable wellbeing.', 'md-new' ),
		),
		'travel'                => array(
			'name'        => __( 'Travel', 'md-new' ),
			'description' => __( 'Destination reporting, practical travel guidance, and cultural coverage.', 'md-new' ),
		),
		'food'                  => array(
			'name'        => __( 'Food', 'md-new' ),
			'description' => __( 'Recipes, culinary technique, restaurant culture, food history, and food science.', 'md-new' ),
		),
		'culture-entertainment' => array(
			'name'        => __( 'Culture and Entertainment', 'md-new' ),
			'description' => __( 'Books, film, television, music, games, and popular-culture criticism.', 'md-new' ),
		),
	);
}

/**
 * Return the configured raw-data base URL.
 *
 * @return string
 */
function gatilab_br_source_base() {
	$base = defined( 'GATILAB_BR_SOURCE_BASE' ) ? GATILAB_BR_SOURCE_BASE : get_option( 'gatilab_br_source_base', GATILAB_BR_DEFAULT_SOURCE );
	$base = esc_url_raw( trailingslashit( (string) $base ), array( 'https' ) );

	if ( empty( $base ) ) {
		return GATILAB_BR_DEFAULT_SOURCE;
	}

	return $base;
}

/**
 * Return the durable option key for a category.
 *
 * @param string $category Category slug.
 * @return string
 */
function gatilab_br_option_key( $category ) {
	return 'gatilab_br_payload_' . sanitize_key( $category );
}

/**
 * Return the performance-cache key for a category.
 *
 * @param string $category Category slug.
 * @return string
 */
function gatilab_br_transient_key( $category ) {
	return 'gatilab_br_cache_' . sanitize_key( $category );
}

/**
 * Return the short negative-cache key for an unavailable category.
 *
 * @param string $category Category slug.
 * @return string
 */
function gatilab_br_failure_key( $category ) {
	return 'gatilab_br_missing_' . sanitize_key( $category );
}

/**
 * Validate one public ranking item.
 *
 * @param mixed $item Item value.
 * @param int   $rank Expected rank.
 * @return bool
 */
function gatilab_br_validate_item( $item, $rank ) {
	if ( ! is_array( $item ) ) {
		return false;
	}

	$required = array( 'rank', 'id', 'name', 'url', 'score', 'movement', 'best_for', 'reason', 'limitation', 'confidence', 'reviewed_at' );
	foreach ( $required as $key ) {
		if ( ! array_key_exists( $key, $item ) ) {
			return false;
		}
	}

	if ( absint( $item['rank'] ) !== $rank || ! preg_match( '/^[a-z0-9-]+$/', (string) $item['id'] ) ) {
		return false;
	}

	$url = wp_parse_url( (string) $item['url'] );
	if ( empty( $url['scheme'] ) || 'https' !== $url['scheme'] || empty( $url['host'] ) ) {
		return false;
	}

	$score = (float) $item['score'];
	if ( 0 > $score || 100 < $score ) {
		return false;
	}

	if ( ! in_array( $item['movement'], array( 'new', 'up', 'down', 'unchanged' ), true ) ) {
		return false;
	}

	if ( ! in_array( $item['confidence'], array( 'high', 'standard', 'provisional' ), true ) ) {
		return false;
	}

	foreach ( array( 'name', 'best_for', 'reason', 'limitation', 'reviewed_at' ) as $text_key ) {
		if ( ! is_string( $item[ $text_key ] ) || '' === trim( $item[ $text_key ] ) ) {
			return false;
		}
	}

	return true;
}

/**
 * Validate a remote category payload before accepting it.
 *
 * @param mixed  $payload  Decoded payload.
 * @param string $category Expected category.
 * @return bool
 */
function gatilab_br_validate_payload( $payload, $category ) {
	$categories = gatilab_br_categories();
	if ( ! isset( $categories[ $category ] ) || ! is_array( $payload ) ) {
		return false;
	}

	if (
		1 !== (int) ( $payload['schema_version'] ?? 0 ) ||
		'Gatilab Blog Rankings' !== ( $payload['project'] ?? '' ) ||
		( $payload['category']['slug'] ?? '' ) !== $category ||
		! preg_match( '/^[0-9]{4}-(0[1-9]|1[0-2])$/', (string) ( $payload['edition'] ?? '' ) ) ||
		! in_array( $payload['status'] ?? '', array( 'beta', 'final' ), true )
	) {
		return false;
	}

	$domains = array();
	foreach ( array( 'independent', 'publisher_company' ) as $track ) {
		$track_data = $payload['tracks'][ $track ] ?? null;
		if ( ! is_array( $track_data ) || ! is_array( $track_data['items'] ?? null ) || 10 !== count( $track_data['items'] ) ) {
			return false;
		}

		$expected_count = 'final' === $payload['status'] ? 100 : 10;
		if ( absint( $track_data['count'] ?? 0 ) !== $expected_count ) {
			return false;
		}

		foreach ( array_values( $track_data['items'] ) as $index => $item ) {
			if ( ! gatilab_br_validate_item( $item, $index + 1 ) ) {
				return false;
			}
			$host = strtolower( (string) wp_parse_url( $item['url'], PHP_URL_HOST ) );
			$host = preg_replace( '/^www\./', '', $host );
			if ( isset( $domains[ $host ] ) ) {
				return false;
			}
			$domains[ $host ] = true;
		}
	}

	return true;
}

/**
 * Log a private refresh error in debug environments.
 *
 * @param string $message Error message.
 * @return void
 */
function gatilab_br_debug_log( $message ) {
	if ( defined( 'WP_DEBUG' ) && WP_DEBUG ) {
		error_log( 'Gatilab Blog Rankings: ' . sanitize_text_field( $message ) ); // phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
	}
}

/**
 * Fetch, validate, and durably store one category payload.
 *
 * @param string $category Category slug.
 * @return array<string, mixed>|null
 */
function gatilab_br_fetch_payload( $category ) {
	$category   = sanitize_key( $category );
	$categories = gatilab_br_categories();
	if ( ! isset( $categories[ $category ] ) ) {
		return null;
	}

	$stored  = get_option( gatilab_br_option_key( $category ), array() );
	$headers = array(
		'Accept'     => 'application/json',
		'User-Agent' => 'Gatilab-Blog-Rankings/' . GATILAB_BR_VERSION . '; ' . home_url( '/' ),
	);
	if ( ! empty( $stored['etag'] ) ) {
		$headers['If-None-Match'] = sanitize_text_field( $stored['etag'] );
	}

	$source_url = gatilab_br_source_base() . rawurlencode( $category ) . '.json';
	$response   = wp_safe_remote_get(
		$source_url,
		array(
			'timeout'             => 12,
			'redirection'         => 3,
			'limit_response_size' => 1048576,
			'headers'             => $headers,
		)
	);

	if ( is_wp_error( $response ) ) {
		gatilab_br_debug_log( $response->get_error_message() );
		if ( ! is_array( $stored['payload'] ?? null ) ) {
			set_transient( gatilab_br_failure_key( $category ), 1, HOUR_IN_SECONDS );
		}
		return is_array( $stored['payload'] ?? null ) ? $stored['payload'] : null;
	}

	$status = wp_remote_retrieve_response_code( $response );
	if ( 304 === $status && is_array( $stored['payload'] ?? null ) ) {
		set_transient( gatilab_br_transient_key( $category ), $stored['payload'], DAY_IN_SECONDS );
		return $stored['payload'];
	}

	if ( 200 !== $status ) {
		gatilab_br_debug_log( sprintf( 'HTTP %d for %s', $status, $category ) );
		if ( ! is_array( $stored['payload'] ?? null ) ) {
			set_transient( gatilab_br_failure_key( $category ), 1, HOUR_IN_SECONDS );
		}
		return is_array( $stored['payload'] ?? null ) ? $stored['payload'] : null;
	}

	$body    = wp_remote_retrieve_body( $response );
	$payload = json_decode( $body, true );
	if ( ! gatilab_br_validate_payload( $payload, $category ) ) {
		gatilab_br_debug_log( sprintf( 'Rejected malformed payload for %s', $category ) );
		if ( ! is_array( $stored['payload'] ?? null ) ) {
			set_transient( gatilab_br_failure_key( $category ), 1, HOUR_IN_SECONDS );
		}
		return is_array( $stored['payload'] ?? null ) ? $stored['payload'] : null;
	}

	$record = array(
		'payload'    => $payload,
		'etag'       => sanitize_text_field( wp_remote_retrieve_header( $response, 'etag' ) ),
		'checksum'   => hash( 'sha256', $body ),
		'fetched_at' => time(),
		'source_url' => $source_url,
	);
	update_option( gatilab_br_option_key( $category ), $record, false );
	set_transient( gatilab_br_transient_key( $category ), $payload, DAY_IN_SECONDS );
	delete_transient( gatilab_br_failure_key( $category ) );

	return $payload;
}

/**
 * Return a cached or last-known-good category payload.
 *
 * @param string $category Category slug.
 * @param bool   $refresh  Force a remote refresh.
 * @return array<string, mixed>|null
 */
function gatilab_br_get_payload( $category, $refresh = false ) {
	$category = sanitize_key( $category );
	if ( $refresh ) {
		return gatilab_br_fetch_payload( $category );
	}
	if ( get_transient( gatilab_br_failure_key( $category ) ) ) {
		return null;
	}

	$cached = get_transient( gatilab_br_transient_key( $category ) );
	if ( is_array( $cached ) && gatilab_br_validate_payload( $cached, $category ) ) {
		return $cached;
	}

	$stored = get_option( gatilab_br_option_key( $category ), array() );
	if ( is_array( $stored['payload'] ?? null ) && gatilab_br_validate_payload( $stored['payload'], $category ) ) {
		set_transient( gatilab_br_transient_key( $category ), $stored['payload'], DAY_IN_SECONDS );
		return $stored['payload'];
	}

	return gatilab_br_fetch_payload( $category );
}

/**
 * Refresh every launch category.
 *
 * @return array<string, bool>
 */
function gatilab_br_refresh_all() {
	$results = array();
	foreach ( array_keys( gatilab_br_categories() ) as $category ) {
		$results[ $category ] = null !== gatilab_br_fetch_payload( $category );
	}
	update_option( 'gatilab_br_last_refresh', time(), false );

	return $results;
}
add_action( GATILAB_BR_CRON_HOOK, 'gatilab_br_refresh_all' );

/**
 * Ensure the daily refresh event exists.
 *
 * @return void
 */
function gatilab_br_schedule_refresh() {
	if ( ! wp_next_scheduled( GATILAB_BR_CRON_HOOK ) ) {
		wp_schedule_event( time() + HOUR_IN_SECONDS, 'daily', GATILAB_BR_CRON_HOOK );
	}
}
add_action( 'init', 'gatilab_br_schedule_refresh' );
add_action( 'after_switch_theme', 'gatilab_br_schedule_refresh' );

/**
 * Remove the scheduled event when this child theme is switched off.
 *
 * @return void
 */
function gatilab_br_clear_schedule() {
	wp_clear_scheduled_hook( GATILAB_BR_CRON_HOOK );
}
add_action( 'switch_theme', 'gatilab_br_clear_schedule' );

/**
 * Return whether the current request uses a rankings template.
 *
 * @return bool
 */
function gatilab_br_is_rankings_template() {
	return is_page_template( 'templates/blog-rankings-hub.php' ) || is_page_template( 'templates/blog-ranking-category.php' );
}

/**
 * Enqueue rankings assets only on the two templates.
 *
 * @return void
 */
function gatilab_br_enqueue_assets() {
	if ( ! gatilab_br_is_rankings_template() ) {
		return;
	}

	$css = MD_CHILD_DIR . 'assets/css/blog-rankings.css';
	$js  = MD_CHILD_DIR . 'assets/js/blog-rankings.js';
	if ( file_exists( $css ) ) {
		wp_enqueue_style( 'gatilab-blog-rankings', MD_CHILD_URL . 'assets/css/blog-rankings.css', array(), (string) filemtime( $css ) );
	}
	if ( file_exists( $js ) ) {
		wp_enqueue_script( 'gatilab-blog-rankings', MD_CHILD_URL . 'assets/js/blog-rankings.js', array(), (string) filemtime( $js ), true );
	}
}
add_action( 'wp_enqueue_scripts', 'gatilab_br_enqueue_assets', 30 );

/**
 * Return the ranking category assigned to the current page.
 *
 * @param int $post_id Optional page ID.
 * @return string
 */
function gatilab_br_page_category( $post_id = 0 ) {
	$post_id  = $post_id ? absint( $post_id ) : get_queried_object_id();
	$category = sanitize_key( get_post_meta( $post_id, '_gatilab_br_category', true ) );
	if ( ! $category ) {
		$category = sanitize_key( get_post_field( 'post_name', $post_id ) );
	}

	return isset( gatilab_br_categories()[ $category ] ) ? $category : '';
}

/**
 * Render movement text.
 *
 * @param string $movement Movement state.
 * @return string
 */
function gatilab_br_movement_label( $movement ) {
	$labels = array(
		'new'       => __( 'New', 'md-new' ),
		'up'        => __( 'Up', 'md-new' ),
		'down'      => __( 'Down', 'md-new' ),
		'unchanged' => __( 'Unchanged', 'md-new' ),
	);

	return $labels[ $movement ] ?? __( 'Unchanged', 'md-new' );
}

/**
 * Render one track's visible Top 10.
 *
 * @param array<string, mixed> $track Track payload.
 * @param string               $track_slug Track slug.
 * @return void
 */
function gatilab_br_render_track( $track, $track_slug ) {
	$items = array_values( $track['items'] ?? array() );
	if ( 10 !== count( $items ) ) {
		return;
	}
	?>
	<section class="gbr-track" id="<?php echo esc_attr( 'gbr-' . $track_slug ); ?>" data-gbr-panel="<?php echo esc_attr( $track_slug ); ?>" aria-labelledby="<?php echo esc_attr( 'gbr-tab-' . $track_slug ); ?>">
		<div class="gbr-track__head">
			<p class="gbr-eyebrow"><?php echo esc_html( $track['label'] ); ?></p>
			<h2><?php /* translators: %s: Ranking track label. */ echo esc_html( sprintf( __( 'Top 10 %s', 'md-new' ), $track['label'] ) ); ?></h2>
			<p><?php esc_html_e( 'Ranks compare publications only inside this category and track.', 'md-new' ); ?></p>
		</div>

		<div class="gbr-podium" role="list">
			<?php foreach ( array_slice( $items, 0, 3 ) as $item ) : ?>
				<article class="gbr-podium__item" role="listitem">
					<div class="gbr-rank" aria-label="<?php /* translators: %d: Ranking position. */ echo esc_attr( sprintf( __( 'Rank %d', 'md-new' ), $item['rank'] ) ); ?>"><?php echo esc_html( $item['rank'] ); ?></div>
					<div class="gbr-podium__copy">
						<h3><a href="<?php echo esc_url( $item['url'] ); ?>" rel="nofollow noopener"><?php echo esc_html( $item['name'] ); ?></a></h3>
						<p class="gbr-best-for"><strong><?php esc_html_e( 'Best for:', 'md-new' ); ?></strong> <?php echo esc_html( $item['best_for'] ); ?></p>
						<p><?php echo esc_html( $item['reason'] ); ?></p>
						<p class="gbr-limit"><strong><?php esc_html_e( 'Limit:', 'md-new' ); ?></strong> <?php echo esc_html( $item['limitation'] ); ?></p>
					</div>
					<div class="gbr-score"><span><?php echo esc_html( number_format_i18n( (float) $item['score'], 1 ) ); ?></span><small><?php esc_html_e( 'score', 'md-new' ); ?></small></div>
				</article>
			<?php endforeach; ?>
		</div>

		<ol class="gbr-list" start="4">
			<?php foreach ( array_slice( $items, 3 ) as $item ) : ?>
				<li class="gbr-list__item">
					<div class="gbr-list__rank" aria-hidden="true"><?php echo esc_html( $item['rank'] ); ?></div>
					<div class="gbr-list__copy">
						<h3><a href="<?php echo esc_url( $item['url'] ); ?>" rel="nofollow noopener"><?php echo esc_html( $item['name'] ); ?></a></h3>
						<p><?php echo esc_html( $item['best_for'] ); ?></p>
					</div>
					<div class="gbr-list__meta">
						<strong><?php echo esc_html( number_format_i18n( (float) $item['score'], 1 ) ); ?></strong>
						<span class="gbr-movement gbr-movement--<?php echo esc_attr( $item['movement'] ); ?>"><?php echo esc_html( gatilab_br_movement_label( $item['movement'] ) ); ?></span>
					</div>
				</li>
			<?php endforeach; ?>
		</ol>

		<p class="gbr-full-list"><a class="gbr-button gbr-button--secondary" href="<?php echo esc_url( $track['markdown_url'] ?? '' ); ?>" rel="nofollow noopener"><?php /* translators: %d: Number of ranked publications. */ echo esc_html( sprintf( __( 'See the complete Top %d on GitHub', 'md-new' ), absint( $track['count'] ) ) ); ?></a></p>
	</section>
	<?php
}

/**
 * Output visible ItemList schema for a category payload.
 *
 * @param array<string, mixed> $payload Category payload.
 * @return void
 */
function gatilab_br_output_schema( $payload ) {
	$graph = array();
	foreach ( array( 'independent', 'publisher_company' ) as $track_slug ) {
		$track = $payload['tracks'][ $track_slug ];
		$list  = array();
		foreach ( $track['items'] as $item ) {
			$list[] = array(
				'@type'    => 'ListItem',
				'position' => absint( $item['rank'] ),
				'url'      => esc_url_raw( $item['url'] ),
				'name'     => sanitize_text_field( $item['name'] ),
			);
		}
		$graph[] = array(
			'@type'           => 'ItemList',
			'name'            => sprintf( '%s: %s', $payload['category']['name'], $track['label'] ),
			'numberOfItems'   => 10,
			'itemListOrder'   => 'https://schema.org/ItemListOrderAscending',
			'itemListElement' => $list,
		);
	}
	$schema = array(
		'@context' => 'https://schema.org',
		'@graph'   => $graph,
	);
	?>
	<script type="application/ld+json"><?php echo wp_json_encode( $schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?></script>
	<?php
}

/**
 * Register public read-only REST routes.
 *
 * @return void
 */
function gatilab_br_register_rest_routes() {
	register_rest_route(
		'gatilab/v1',
		'/blog-rankings',
		array(
			'methods'             => WP_REST_Server::READABLE,
			'permission_callback' => '__return_true',
			'callback'            => function () {
				$items = array();
				foreach ( gatilab_br_categories() as $slug => $category ) {
					$payload = gatilab_br_get_payload( $slug );
					$items[]  = array(
						'slug'        => $slug,
						'name'        => $category['name'],
						'description' => $category['description'],
						'edition'     => $payload['edition'] ?? null,
						'status'      => $payload['status'] ?? 'planned',
					);
				}
				return rest_ensure_response( array( 'categories' => $items ) );
			},
		)
	);

	register_rest_route(
		'gatilab/v1',
		'/blog-rankings/(?P<category>[a-z0-9-]+)',
		array(
			'methods'             => WP_REST_Server::READABLE,
			'permission_callback' => '__return_true',
			'args'                => array(
				'category' => array(
					'sanitize_callback' => 'sanitize_key',
					'validate_callback' => function ( $value ) {
						return isset( gatilab_br_categories()[ $value ] );
					},
				),
			),
			'callback'            => function ( WP_REST_Request $request ) {
				$payload = gatilab_br_get_payload( $request['category'] );
				if ( ! $payload ) {
					return new WP_Error( 'gatilab_br_not_available', __( 'This ranking is not available yet.', 'md-new' ), array( 'status' => 404 ) );
				}
				return rest_ensure_response( $payload );
			},
		)
	);
}
add_action( 'rest_api_init', 'gatilab_br_register_rest_routes' );

/**
 * Register the rankings status page.
 *
 * @return void
 */
function gatilab_br_admin_menu() {
	add_management_page(
		__( 'Blog Rankings', 'md-new' ),
		__( 'Blog Rankings', 'md-new' ),
		'manage_options',
		'gatilab-blog-rankings',
		'gatilab_br_admin_page'
	);
}
add_action( 'admin_menu', 'gatilab_br_admin_menu' );

/**
 * Handle an authenticated manual refresh.
 *
 * @return void
 */
function gatilab_br_admin_refresh() {
	if ( ! current_user_can( 'manage_options' ) ) {
		wp_die( esc_html__( 'You do not have permission to refresh rankings.', 'md-new' ) );
	}
	check_admin_referer( 'gatilab_br_refresh' );
	gatilab_br_refresh_all();
	wp_safe_redirect( add_query_arg( 'refreshed', '1', admin_url( 'tools.php?page=gatilab-blog-rankings' ) ) );
	exit;
}
add_action( 'admin_post_gatilab_br_refresh', 'gatilab_br_admin_refresh' );

/**
 * Render the private rankings status screen.
 *
 * @return void
 */
function gatilab_br_admin_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	?>
	<div class="wrap">
		<h1><?php esc_html_e( 'Gatilab Blog Rankings', 'md-new' ); ?></h1>
		<?php if ( isset( $_GET['refreshed'] ) ) : // phpcs:ignore WordPress.Security.NonceVerification.Recommended ?>
			<div class="notice notice-success is-dismissible"><p><?php esc_html_e( 'Ranking refresh completed. Invalid or unavailable payloads kept their previous accepted edition.', 'md-new' ); ?></p></div>
		<?php endif; ?>
		<p><?php esc_html_e( 'The public page always serves a validated last-known-good edition.', 'md-new' ); ?></p>
		<table class="widefat striped">
			<thead><tr><th><?php esc_html_e( 'Category', 'md-new' ); ?></th><th><?php esc_html_e( 'Edition', 'md-new' ); ?></th><th><?php esc_html_e( 'Status', 'md-new' ); ?></th><th><?php esc_html_e( 'Last accepted', 'md-new' ); ?></th></tr></thead>
			<tbody>
			<?php foreach ( gatilab_br_categories() as $slug => $category ) : ?>
				<?php $record = get_option( gatilab_br_option_key( $slug ), array() ); ?>
				<tr>
					<td><?php echo esc_html( $category['name'] ); ?></td>
					<td><?php echo esc_html( $record['payload']['edition'] ?? '—' ); ?></td>
					<td><?php echo esc_html( $record['payload']['status'] ?? __( 'Planned', 'md-new' ) ); ?></td>
					<td><?php echo ! empty( $record['fetched_at'] ) ? esc_html( wp_date( 'Y-m-d H:i:s T', absint( $record['fetched_at'] ) ) ) : esc_html__( 'Never', 'md-new' ); ?></td>
				</tr>
			<?php endforeach; ?>
			</tbody>
		</table>
		<form action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" method="post">
			<input type="hidden" name="action" value="gatilab_br_refresh">
			<?php wp_nonce_field( 'gatilab_br_refresh' ); ?>
			<?php submit_button( __( 'Refresh rankings now', 'md-new' ) ); ?>
		</form>
	</div>
	<?php
}
