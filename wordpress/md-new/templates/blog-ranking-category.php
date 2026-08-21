<?php
/**
 * Template Name: Gatilab Blog Ranking Category
 * Template Post Type: page
 *
 * @package MD_New
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$category         = gatilab_br_page_category();
$categories       = gatilab_br_categories();
$payload          = $category ? gatilab_br_get_payload( $category ) : null;
$category_graphic = gatilab_br_featured_graphic_url();

get_header();
?>
<main id="content" class="gbr gbr-category">
	<?php if ( $category && isset( $categories[ $category ] ) && $payload ) : ?>
		<?php
		$independent                 = $payload['tracks']['independent'];
		$publisher                   = $payload['tracks']['publisher_company'];
		$independent['markdown_url'] = $payload['links']['independent_markdown'];
		$publisher['markdown_url']   = $payload['links']['publisher_company_markdown'];
		?>
		<header class="gbr-hero gbr-hero--category" aria-labelledby="gbr-title">
			<div class="gbr-wrap gbr-hero__grid">
				<div class="gbr-hero__copy">
					<p class="gbr-eyebrow"><?php /* translators: 1: Ranking edition. 2: Ranking status. */ echo esc_html( sprintf( __( '%1$s edition · %2$s', 'md-new' ), $payload['edition'], ucfirst( $payload['status'] ) ) ); ?></p>
					<h1 id="gbr-title"><?php /* translators: %s: Ranking category name. */ echo esc_html( sprintf( __( '%s Blog Rankings', 'md-new' ), $payload['category']['name'] ) ); ?></h1>
					<p class="gbr-hero__lede"><?php echo esc_html( $payload['category']['description'] ); ?></p>
					<p class="gbr-hero__meta">
						<?php if ( 'beta' === $payload['status'] ) : ?>
							<?php esc_html_e( 'Independent and company-owned publications are ranked separately. Beta results are provisional.', 'md-new' ); ?>
						<?php else : ?>
							<?php esc_html_e( 'Independent and company-owned publications are ranked separately. The complete Top 100 for each track is published in GitHub.', 'md-new' ); ?>
						<?php endif; ?>
					</p>
				</div>
				<div class="gbr-hero__visual gbr-hero__visual--category">
					<img src="<?php echo esc_url( $category_graphic ? $category_graphic : MD_CHILD_URL . 'assets/images/blog-rankings/' . $category . '.svg' ); ?>" alt="<?php /* translators: %s: Ranking category name. */ echo esc_attr( sprintf( __( '%s Blog Rankings showing the Top 3 publications in both ranking tracks.', 'md-new' ), $payload['category']['name'] ) ); ?>" width="1600" height="900" fetchpriority="high" decoding="async">
				</div>
			</div>
		</header>

		<div class="gbr-track-nav" role="tablist" aria-label="<?php esc_attr_e( 'Ranking tracks', 'md-new' ); ?>">
			<div class="gbr-wrap gbr-track-nav__inner">
				<button type="button" id="gbr-tab-independent" class="gbr-track-nav__button is-active" data-gbr-tab="independent" role="tab" aria-selected="true" aria-controls="gbr-independent"><?php esc_html_e( 'Independent Blogs', 'md-new' ); ?></button>
				<button type="button" id="gbr-tab-publisher_company" class="gbr-track-nav__button" data-gbr-tab="publisher_company" role="tab" aria-selected="false" aria-controls="gbr-publisher_company"><?php esc_html_e( 'Publisher and Company Blogs', 'md-new' ); ?></button>
			</div>
		</div>

		<div class="gbr-section gbr-section--canvas">
			<div class="gbr-wrap">
				<?php gatilab_br_render_track( $independent, 'independent' ); ?>
				<?php gatilab_br_render_track( $publisher, 'publisher_company' ); ?>
			</div>
		</div>

		<section class="gbr-section gbr-section--alt" aria-labelledby="gbr-limits-title">
			<div class="gbr-wrap gbr-limits">
				<div>
					<p class="gbr-eyebrow"><?php esc_html_e( 'The boundary', 'md-new' ); ?></p>
					<h2 id="gbr-limits-title"><?php esc_html_e( 'What This Rank Does Not Prove', 'md-new' ); ?></h2>
				</div>
				<p><?php esc_html_e( 'A position compares one publication with others in the same category, track, edition, and evidence window. It does not certify every claim, author, product, or business connected to that publication.', 'md-new' ); ?></p>
			</div>
		</section>

		<section class="gbr-section gbr-section--deep gbr-close" aria-labelledby="gbr-correct-title">
			<div class="gbr-wrap">
				<p class="gbr-eyebrow"><?php esc_html_e( 'Keep the ranking honest', 'md-new' ); ?></p>
				<h2 id="gbr-correct-title"><?php esc_html_e( 'Nominate, Correct, or Appeal', 'md-new' ); ?></h2>
				<p><?php esc_html_e( 'Use the public forms so evidence and decisions remain attached to the versioned record.', 'md-new' ); ?></p>
				<div class="gbr-actions">
					<a class="gbr-button gbr-button--primary" href="https://github.com/wpgaurav/blog-rankings/issues/new/choose" rel="nofollow noopener"><?php esc_html_e( 'Open the contribution forms', 'md-new' ); ?></a>
					<a class="gbr-button gbr-button--ghost" href="<?php echo esc_url( $payload['links']['methodology'] ); ?>" rel="nofollow noopener"><?php esc_html_e( 'Read the full methodology', 'md-new' ); ?></a>
				</div>
			</div>
		</section>
		<?php gatilab_br_output_schema( $payload ); ?>
	<?php else : ?>
		<section class="gbr-section gbr-section--canvas gbr-empty" aria-labelledby="gbr-empty-title">
			<div class="gbr-wrap">
				<p class="gbr-eyebrow"><?php esc_html_e( 'Ranking unavailable', 'md-new' ); ?></p>
				<h1 id="gbr-empty-title"><?php esc_html_e( 'This Category Is Still Being Reviewed', 'md-new' ); ?></h1>
				<p><?php esc_html_e( 'No incomplete or malformed remote dataset will replace an accepted edition.', 'md-new' ); ?></p>
				<a class="gbr-button gbr-button--secondary" href="<?php echo esc_url( home_url( '/blog-rankings/' ) ); ?>"><?php esc_html_e( 'Return to Blog Rankings', 'md-new' ); ?></a>
			</div>
		</section>
	<?php endif; ?>
</main>
<?php
get_footer();
