<?php
/**
 * Template Name: Gatilab Blog Rankings Hub
 * Template Post Type: page
 *
 * @package MD_New
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

get_header();
$categories = gatilab_br_categories();
?>
<main id="content" class="gbr gbr-hub">
	<header class="gbr-hero" aria-labelledby="gbr-title">
		<div class="gbr-wrap gbr-hero__grid">
			<div class="gbr-hero__copy">
				<p class="gbr-eyebrow"><?php esc_html_e( 'Gatilab Research', 'md-new' ); ?></p>
				<h1 id="gbr-title"><?php esc_html_e( 'Gatilab Blog Rankings', 'md-new' ); ?></h1>
				<p class="gbr-hero__lede"><?php esc_html_e( 'A public, versioned award for useful blogs. Public signals find candidates, human review sets the order, and Git history records every edition.', 'md-new' ); ?></p>
				<div class="gbr-actions">
					<a class="gbr-button gbr-button--primary" href="#categories"><?php esc_html_e( 'Explore the rankings', 'md-new' ); ?></a>
					<a class="gbr-button gbr-button--ghost" href="https://github.com/wpgaurav/blog-rankings/blob/main/METHODOLOGY.md" rel="nofollow noopener"><?php esc_html_e( 'Read the methodology', 'md-new' ); ?></a>
				</div>
				<p class="gbr-hero__meta"><?php esc_html_e( '10 categories. 2 separate tracks. Updated through reviewed monthly releases.', 'md-new' ); ?></p>
			</div>
			<div class="gbr-hero__visual" aria-label="<?php esc_attr_e( 'Three rising ranking bars connected by a measured movement line.', 'md-new' ); ?>">
				<span class="gbr-hero__bar gbr-hero__bar--one"></span>
				<span class="gbr-hero__bar gbr-hero__bar--two"></span>
				<span class="gbr-hero__bar gbr-hero__bar--three"></span>
				<svg viewBox="0 0 300 190" aria-hidden="true" focusable="false"><path d="M44 146 L150 92 L256 30"/><circle cx="44" cy="146" r="7"/><circle cx="150" cy="92" r="7"/><circle cx="256" cy="30" r="7"/></svg>
			</div>
		</div>
	</header>

	<section class="gbr-section gbr-section--canvas" id="categories" aria-labelledby="gbr-categories-title">
		<div class="gbr-wrap">
			<div class="gbr-heading">
				<p class="gbr-eyebrow"><?php esc_html_e( 'The award directory', 'md-new' ); ?></p>
				<h2 id="gbr-categories-title"><?php esc_html_e( 'Blog Rankings by Topic', 'md-new' ); ?></h2>
				<p><?php esc_html_e( 'Each topic separates independent publications from company and institutional publishers. The Top 10 appears on Gatilab; the complete edition lives in GitHub.', 'md-new' ); ?></p>
			</div>

			<div class="gbr-directory">
				<?php foreach ( $categories as $slug => $category ) : ?>
					<?php
					$payload      = gatilab_br_get_payload( $slug );
					$ranking_page = get_page_by_path( 'blog-rankings/' . $slug, OBJECT, 'page' );
					$url          = $ranking_page ? get_permalink( $ranking_page ) : '';
					?>
					<article class="gbr-directory__item">
						<div class="gbr-directory__copy">
							<p class="gbr-directory__status"><?php /* translators: 1: Ranking edition. 2: Ranking status. */ echo esc_html( $payload ? sprintf( __( '%1$s edition · %2$s', 'md-new' ), $payload['edition'], ucfirst( $payload['status'] ) ) : __( 'Planned', 'md-new' ) ); ?></p>
							<h3><?php echo esc_html( $category['name'] ); ?></h3>
							<p><?php echo esc_html( $category['description'] ); ?></p>
						</div>
						<?php if ( $url && $payload ) : ?>
							<a class="gbr-directory__link" href="<?php echo esc_url( $url ); ?>"><?php esc_html_e( 'View rankings', 'md-new' ); ?><span aria-hidden="true">→</span></a>
						<?php else : ?>
							<span class="gbr-directory__planned"><?php esc_html_e( 'Research in progress', 'md-new' ); ?></span>
						<?php endif; ?>
					</article>
				<?php endforeach; ?>
			</div>
		</div>
	</section>

	<section class="gbr-section gbr-section--alt" aria-labelledby="gbr-method-title">
		<div class="gbr-wrap gbr-method">
			<div class="gbr-heading">
				<p class="gbr-eyebrow"><?php esc_html_e( 'How ranking works', 'md-new' ); ?></p>
				<h2 id="gbr-method-title"><?php esc_html_e( 'Popularity Is Only 20% of the Score', 'md-new' ); ?></h2>
				<p><?php esc_html_e( 'Editorial quality carries the most weight. Trust, reach, publishing consistency, user experience, and community impact complete the score.', 'md-new' ); ?></p>
			</div>
			<dl class="gbr-weights">
				<div><dt><?php esc_html_e( 'Editorial quality', 'md-new' ); ?></dt><dd><span style="--gbr-width:100%"></span><strong>30%</strong></dd></div>
				<div><dt><?php esc_html_e( 'Trust', 'md-new' ); ?></dt><dd><span style="--gbr-width:66.67%"></span><strong>20%</strong></dd></div>
				<div><dt><?php esc_html_e( 'Reach', 'md-new' ); ?></dt><dd><span style="--gbr-width:66.67%"></span><strong>20%</strong></dd></div>
				<div><dt><?php esc_html_e( 'Freshness', 'md-new' ); ?></dt><dd><span style="--gbr-width:50%"></span><strong>15%</strong></dd></div>
				<div><dt><?php esc_html_e( 'UX', 'md-new' ); ?></dt><dd><span style="--gbr-width:33.33%"></span><strong>10%</strong></dd></div>
				<div><dt><?php esc_html_e( 'Impact', 'md-new' ); ?></dt><dd><span style="--gbr-width:16.67%"></span><strong>5%</strong></dd></div>
			</dl>
		</div>
	</section>

	<section class="gbr-section gbr-section--deep gbr-close" aria-labelledby="gbr-close-title">
		<div class="gbr-wrap">
			<p class="gbr-eyebrow"><?php esc_html_e( 'Help improve the record', 'md-new' ); ?></p>
			<h2 id="gbr-close-title"><?php esc_html_e( 'Nominate a Blog or Correct a Fact', 'md-new' ); ?></h2>
			<p><?php esc_html_e( 'The public issue forms keep evidence, decisions, and corrections attached to the same versioned record.', 'md-new' ); ?></p>
			<div class="gbr-actions">
				<a class="gbr-button gbr-button--primary" href="https://github.com/wpgaurav/blog-rankings/issues/new/choose" rel="nofollow noopener"><?php esc_html_e( 'Open the contribution forms', 'md-new' ); ?></a>
				<a class="gbr-button gbr-button--ghost" href="https://github.com/wpgaurav/blog-rankings" rel="nofollow noopener"><?php esc_html_e( 'Browse the public repository', 'md-new' ); ?></a>
			</div>
		</div>
	</section>
</main>
<?php
get_footer();
